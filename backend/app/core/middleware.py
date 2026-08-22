"""CORS / CSP / HSTS / GZip / TraceID / 限流中间件。"""

import contextvars
import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.database import redis_client

# 请求级 Trace ID 上下文，供 ok()/error() 注入响应体
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default=""
)

# 令牌桶 Lua 脚本（设计文档 §1.4.1/§11.2，算法：令牌桶）
# KEYS[1] = rate:{ip}:{route}
# ARGV[1] = capacity（桶容量，即最大令牌数）
# ARGV[2] = refill_time（补充到满所需秒数，即每 token 间隔 = refill_time/capacity）
# 返回值：1 = 允许（消耗 1 令牌），0 = 限流
_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_time = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local data = redis.call('HMGET', key, 'tokens', 'last_ts')
local tokens = tonumber(data[1])
local last_ts = tonumber(data[2])

if tokens == nil then
    -- 首次访问：桶满
    tokens = capacity
    last_ts = now
else
    -- 计算补充令牌：(now - last_ts) / refill_time * capacity
    local elapsed = now - last_ts
    local refill = elapsed * capacity / refill_time
    if refill > 0 then
        tokens = math.min(capacity, tokens + refill)
        last_ts = now
    end
end

if tokens >= 1 then
    tokens = tokens - 1
    redis.call('HMSET', key, 'tokens', tokens, 'last_ts', last_ts)
    -- TTL = refill_time * 2（保证断流后桶能重置，避免僵尸键）
    redis.call('EXPIRE', key, math.ceil(refill_time * 2))
    return 1
else
    -- 令牌不足，更新 last_ts（不补充令牌）
    redis.call('HMSET', key, 'tokens', tokens, 'last_ts', last_ts)
    redis.call('EXPIRE', key, math.ceil(refill_time * 2))
    return 0
end
"""

# LLM 路由前缀（调用 LLM 生成能力的端点，适用更严限流）
# 设计文档 §1.4.1：LLM 接口 10 req/min
_LLM_ROUTE_PREFIXES = (
    "/api/v1/match/compare",       # 人岗比对（语义 + LLM 诊断）
    "/api/v1/match/recommend",     # 批量推荐（LLM 增强）
    "/api/v1/match/result/",       # 匹配结果详情含 diagnosis
    "/api/v1/match/diagnosis",     # 诊断报告生成
    "/api/v1/resume/parse",        # 简历解析（LLM 抽取）
    "/api/v1/resume/extract",      # 简历技能提取
    "/api/v1/admin/crawl/trigger", # 爬虫触发（防滥用）
)


def setup_middleware(app: FastAPI) -> None:
    """按顺序注册所有中间件。"""

    # CORS — 可配置白名单模式；通配 origin（开发默认）时不允许携带凭据
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials="*" not in settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # GZip — 响应体 > 1KB 自动压缩
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # 限流 — 令牌桶（设计文档 §1.4.1/§11.2，错误码 4290）
    app.add_middleware(RateLimitMiddleware)

    # CSP / HSTS — 自定义响应头
    app.add_middleware(SecurityHeadersMiddleware)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """按 (IP, 路由) 的令牌桶限流（设计文档 §1.4.1/§11.2）。

    普通接口 100 req/min，LLM 生成类 10 req/min。
    键空间 `rate:{ip}:{route}` 对齐设计文档 §11.4.4。
    Redis 不可用时降级放行（限流是增强能力，不拖垮 API）。

    令牌桶算法：
    - capacity = 限流阈值（桶容量）
    - refill_time = 60s（每分钟补充到满）
    - 每次请求消耗 1 令牌，令牌不足返回 429
    - Lua 脚本保证原子性，避免竞态条件
    """

    GENERAL_CAPACITY = 100   # 普通接口：100 req/min
    LLM_CAPACITY = 10        # LLM 接口：10 req/min
    REFILL_SECONDS = 60      # 60 秒补充到满

    @staticmethod
    def _client_ip(request: Request) -> str:
        """生产信任 X-Forwarded-For（负载均衡终止 TLS），开发取 peer IP。"""
        if settings.is_production:
            xff = request.headers.get("x-forwarded-for", "")
            if xff:
                return xff.split(",")[0].strip()
        return request.client.host if request.client else ""

    @staticmethod
    def _is_llm_route(path: str) -> bool:
        """判断是否为 LLM 生成类路由（适用更严限流）。"""
        for prefix in _LLM_ROUTE_PREFIXES:
            if path.startswith(prefix):
                return True
        # diagnosis 子路径
        if path.endswith("/diagnosis"):
            return True
        return False

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        # 仅限流 API 路由；认证端（登录/注册/刷新）、健康检查与静态资源放行
        if not path.startswith("/api/v1") or path.startswith("/api/v1/auth/"):
            return await call_next(request)
        ip = self._client_ip(request)
        if not ip:
            return await call_next(request)

        capacity = self.LLM_CAPACITY if self._is_llm_route(path) else self.GENERAL_CAPACITY
        key = f"rate:{ip}:{path}"

        try:
            now = time.time()
            allowed = await redis_client.eval(
                _TOKEN_BUCKET_LUA,
                1,                # 1 个 key
                key,              # KEYS[1]
                capacity,         # ARGV[1]
                self.REFILL_SECONDS,  # ARGV[2]
                now,              # ARGV[3]
            )
        except Exception:
            # Redis 不可用 / Lua 执行失败 → fail-open，不阻塞主调用链
            return await call_next(request)

        if not allowed:
            # 手动构造统一响应体（避免 import schemas.common 造成循环依赖）
            return JSONResponse(
                status_code=429,
                content={
                    "code": 4290,
                    "msg": "请求过于频繁，请稍后再试",
                    "data": None,
                    "trace_id": trace_id_var.get(""),
                },
                headers={
                    "Retry-After": str(self.REFILL_SECONDS // capacity + 1),
                },
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Trace ID：服务端生成（不信任客户端传入），供响应头与 ok()/error() 注入响应体
        trace_id = str(uuid.uuid4().hex[:16])
        trace_id_var.set(trace_id)

        response = await call_next(request)

        # CSP
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "worker-src 'self' blob:; "
            "img-src 'self' data: https:"
        )

        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        response.headers["X-Trace-ID"] = trace_id

        return response
