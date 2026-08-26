"""限流中间件单元测试（T-10，设计文档 §1.4.1/§11.2/§11.4.4）。

测试策略：
- mock redis_client.eval，模拟令牌桶 Lua 脚本行为（纯 Python 实现）
- 用 FastAPI TestClient 发请求，验证中间件行为
- 覆盖：普通接口限流、LLM 接口限流、Redis 故障 fail-open、
  认证端点放行、健康检查放行、Retry-After 响应头、IP 识别
"""

import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import (
    RateLimitMiddleware,
    _LLM_ROUTE_PREFIXES,
    _TOKEN_BUCKET_LUA,
    setup_middleware,
)
from app.core.config import settings


# ---------- 令牌桶 Lua 脚本的 Python 模拟（用于 mock redis.eval）----------

class TokenBucketSimulator:
    """模拟 Redis Lua 令牌桶脚本行为，便于单元测试。"""

    def __init__(self):
        self.buckets: dict[str, dict] = {}  # key -> {tokens, last_ts}

    def eval(self, script: str, numkeys: int, *args) -> int:
        """模拟 redis.eval。验证脚本是令牌桶脚本后执行模拟。"""
        assert script == _TOKEN_BUCKET_LUA, "非预期的 Lua 脚本"
        assert numkeys == 1
        key = args[0]
        capacity = float(args[1])
        refill_time = float(args[2])
        now = float(args[3])

        b = self.buckets.get(key)
        if b is None:
            tokens = capacity
            last_ts = now
        else:
            tokens = b["tokens"]
            last_ts = b["last_ts"]
            elapsed = now - last_ts
            refill = elapsed * capacity / refill_time
            if refill > 0:
                tokens = min(capacity, tokens + refill)
                last_ts = now

        if tokens >= 1:
            tokens -= 1
            self.buckets[key] = {"tokens": tokens, "last_ts": last_ts}
            return 1
        else:
            self.buckets[key] = {"tokens": tokens, "last_ts": last_ts}
            return 0

    def reset(self):
        self.buckets.clear()


# ---------- 测试用 FastAPI 应用 ----------

def _build_test_app() -> FastAPI:
    app = FastAPI()
    setup_middleware(app)

    @app.get("/api/v1/graph/panorama")
    async def panorama():
        return {"code": 0, "msg": "ok", "data": {"nodes": 100}}

    @app.get("/api/v1/match/compare")
    async def match_compare():
        return {"code": 0, "msg": "ok", "data": {"score": 0.85}}

    @app.get("/api/v1/match/result/abc123/diagnosis")
    async def diagnosis():
        return {"code": 0, "msg": "ok", "data": {"report": "..."}}

    @app.post("/api/v1/resume/parse")
    async def resume_parse():
        return {"code": 0, "msg": "ok", "data": {"task_id": "t1"}}

    @app.post("/api/v1/auth/login")
    async def login():
        return {"code": 0, "msg": "ok", "data": {"token": "xxx"}}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


@pytest.fixture
def app():
    return _build_test_app()


@pytest.fixture
def bucket_sim():
    return TokenBucketSimulator()


@pytest.fixture
def mock_redis_eval(bucket_sim):
    """mock redis_client.eval 为令牌桶模拟器。"""
    with patch(
        "app.core.middleware.redis_client",
        new_callable=lambda: _MockRedis(bucket_sim),
    ):
        yield bucket_sim


class _MockRedis:
    """模拟 redis async 客户端的 eval 方法。"""

    def __init__(self, sim: TokenBucketSimulator):
        self._sim = sim
        self.eval = AsyncMock(side_effect=self._sim.eval)


# ---------- 测试用例 ----------


class TestRateLimitGeneral:
    """普通接口限流（100 req/min）。"""

    def test_under_limit_allowed(self, app, mock_redis_eval):
        """请求量在限制内 → 全部 200。"""
        client = TestClient(app)
        for _ in range(5):
            r = client.get("/api/v1/graph/panorama")
            assert r.status_code == 200

    def test_exact_capacity_allowed(self, app, mock_redis_eval):
        """恰好 100 次请求 → 全部通过。"""
        client = TestClient(app)
        for i in range(100):
            r = client.get("/api/v1/graph/panorama")
            assert r.status_code == 200, f"第 {i+1} 次请求意外限流"

    def test_over_limit_blocked(self, app, mock_redis_eval):
        """超过 100 次 → 第 101 次返回 429 + 4290 错误码。"""
        client = TestClient(app)
        for _ in range(100):
            client.get("/api/v1/graph/panorama")

        r = client.get("/api/v1/graph/panorama")
        assert r.status_code == 429
        body = r.json()
        assert body["code"] == 4290
        assert "请求过于频繁" in body["msg"]
        assert body["data"] is None

    def test_retry_after_header(self, app, mock_redis_eval):
        """限流响应包含 Retry-After 头。"""
        client = TestClient(app)
        for _ in range(100):
            client.get("/api/v1/graph/panorama")

        r = client.get("/api/v1/graph/panorama")
        assert "Retry-After" in r.headers
        retry_after = int(r.headers["Retry-After"])
        assert 1 <= retry_after <= 60

    def test_per_route_isolation(self, app, mock_redis_eval):
        """不同路由的限流计数互相独立。"""
        client = TestClient(app)
        # 耗尽 panorama 的令牌
        for _ in range(100):
            client.get("/api/v1/graph/panorama")

        # 另一个路由仍有完整令牌
        r = client.get("/api/v1/match/compare")
        assert r.status_code == 200

    def test_per_ip_isolation(self, app, mock_redis_eval):
        """不同 IP 的限流计数互相独立（生产环境信任 X-Forwarded-For）。"""
        client = TestClient(app)
        # 模拟生产环境以启用 X-Forwarded-For 解析
        # is_production 是 property，patch 其底层字段 app_env
        with patch.object(
            type(settings), "is_production", new_callable=lambda: property(lambda self: True)
        ):
            # IP 1：耗尽 panorama
            for _ in range(100):
                client.get(
                    "/api/v1/graph/panorama",
                    headers={"X-Forwarded-For": "10.0.0.1"},
                )
            r1 = client.get(
                "/api/v1/graph/panorama",
                headers={"X-Forwarded-For": "10.0.0.1"},
            )
            assert r1.status_code == 429

            # IP 2：仍可访问
            r2 = client.get(
                "/api/v1/graph/panorama",
                headers={"X-Forwarded-For": "10.0.0.2"},
            )
            assert r2.status_code == 200


class TestRateLimitLLM:
    """LLM 接口限流（10 req/min，更严格）。"""

    def test_llm_route_lower_limit(self, app, mock_redis_eval):
        """LLM 接口只有 10 令牌，第 11 次被限流。"""
        client = TestClient(app)
        for i in range(10):
            r = client.get("/api/v1/match/compare")
            assert r.status_code == 200, f"第 {i+1} 次 LLM 请求意外限流"

        r = client.get("/api/v1/match/compare")
        assert r.status_code == 429

    def test_diagnosis_subpath_is_llm(self, app, mock_redis_eval):
        """diagnosis 子路径视为 LLM 路由。"""
        client = TestClient(app)
        for _ in range(10):
            client.get("/api/v1/match/result/abc123/diagnosis")

        r = client.get("/api/v1/match/result/abc123/diagnosis")
        assert r.status_code == 429

    def test_resume_parse_is_llm(self, app, mock_redis_eval):
        """resume/parse 视为 LLM 路由。"""
        client = TestClient(app)
        for _ in range(10):
            client.post("/api/v1/resume/parse")

        r = client.post("/api/v1/resume/parse")
        assert r.status_code == 429

    def test_llm_retry_after_smaller(self, app, mock_redis_eval):
        """LLM 限流的 Retry-After 比普通接口长（容量更小）。"""
        client = TestClient(app)
        # 普通接口限流
        for _ in range(100):
            client.get("/api/v1/graph/panorama")
        r_general = client.get("/api/v1/graph/panorama")
        retry_general = int(r_general.headers["Retry-After"])

        # 重置 mock，测试 LLM
        mock_redis_eval.reset()
        for _ in range(10):
            client.get("/api/v1/match/compare")
        r_llm = client.get("/api/v1/match/compare")
        retry_llm = int(r_llm.headers["Retry-After"])

        # LLM 容量小 → 补充间隔长 → Retry-After 更大
        assert retry_llm > retry_general


class TestRateLimitBypass:
    """应放行的端点（认证、健康检查、非 API 路由）。"""

    def test_auth_endpoint_bypassed(self, app, mock_redis_eval):
        """认证端点不限流。"""
        client = TestClient(app)
        # 即使发起很多次也不触发限流
        for _ in range(200):
            r = client.post("/api/v1/auth/login")
            assert r.status_code == 200

    def test_health_endpoint_bypassed(self, app, mock_redis_eval):
        """健康检查端点不限流。"""
        client = TestClient(app)
        for _ in range(200):
            r = client.get("/health")
            assert r.status_code == 200

    def test_non_api_bypassed(self, app, mock_redis_eval):
        """非 /api/v1 路径不限流。"""
        client = TestClient(app)
        for _ in range(200):
            r = client.get("/docs")  # FastAPI 自动生成的文档
            # 可能 404 或 200，但不能是 429
            assert r.status_code != 429


class TestRedisFailOpen:
    """Redis 故障时 fail-open（不阻塞主调用链）。"""

    def test_redis_error_passes(self, app):
        """Redis eval 抛异常 → 请求放行。"""
        with patch(
            "app.core.middleware.redis_client.eval",
            new_callable=lambda: AsyncMock(side_effect=ConnectionError("Redis down")),
        ):
            client = TestClient(app)
            # 大量请求都不会被限流
            for _ in range(50):
                r = client.get("/api/v1/graph/panorama")
                assert r.status_code == 200


class TestTokenBucketRefill:
    """令牌桶补充机制（时间推进后令牌恢复）。"""

    def test_tokens_refill_after_time(self, app, bucket_sim, mock_redis_eval):
        """耗尽令牌后等待足够时间 → 令牌补充，请求恢复通过。"""
        client = TestClient(app)
        # 用 LLM 路由（容量 10，补充快，便于测试）
        for _ in range(10):
            client.get("/api/v1/match/compare")

        r1 = client.get("/api/v1/match/compare")
        assert r1.status_code == 429, "预期已限流"

        # 模拟时间推进 30 秒（半分钟 → 补充一半令牌 = 5）
        # 直接操作模拟器，把 last_ts 往回调
        key = "rate:testclient:/api/v1/match/compare"
        assert key in bucket_sim.buckets
        bucket_sim.buckets[key]["last_ts"] -= 30.0

        # 应该能通过 5 次
        for i in range(5):
            r = client.get("/api/v1/match/compare")
            assert r.status_code == 200, f"补充后第 {i+1} 次请求意外限流"

        # 第 6 次又被限流
        r2 = client.get("/api/v1/match/compare")
        assert r2.status_code == 429, "补充 5 个令牌后第 6 次应被限流"

    def test_full_refill_after_window(self, app, bucket_sim, mock_redis_eval):
        """经过完整补充周期 → 桶恢复满。"""
        client = TestClient(app)
        for _ in range(100):
            client.get("/api/v1/graph/panorama")

        # 时间推进 60s → 完整补充
        key = "rate:testclient:/api/v1/graph/panorama"
        bucket_sim.buckets[key]["last_ts"] -= 60.0

        # 又能通过 100 次
        for _ in range(100):
            r = client.get("/api/v1/graph/panorama")
            assert r.status_code == 200


class TestLLMRouteDetection:
    """LLM 路由识别逻辑。"""

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("/api/v1/match/compare", True),
            ("/api/v1/match/compare/123", True),
            ("/api/v1/match/recommend", True),
            ("/api/v1/match/result/abc/diagnosis", True),
            ("/api/v1/match/diagnosis", True),
            ("/api/v1/resume/parse", True),
            ("/api/v1/resume/extract", True),
            ("/api/v1/admin/crawl/trigger", True),
            ("/api/v1/graph/panorama", False),
            ("/api/v1/graph/position/123", False),
            ("/api/v1/resume/list", False),
            ("/api/v1/auth/login", False),
            ("/api/v1/admin/users", False),
            ("/health", False),
        ],
    )
    def test_is_llm_route(self, path, expected):
        assert RateLimitMiddleware._is_llm_route(path) == expected

    def test_llm_route_prefixes_count(self):
        """LLM 路由前缀数量合理（覆盖主要 LLM 端点）。"""
        assert len(_LLM_ROUTE_PREFIXES) >= 5
