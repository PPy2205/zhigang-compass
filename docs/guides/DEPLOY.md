# 智岗罗盘部署指南

> 项目编号：XH-202621 · 科大讯飞挑战杯揭榜挂帅
> 文档版本：1.0 · 2026.08.26

---

## 目录

- [1. 环境要求](#1-环境要求)
- [2. 快速部署（Docker 一键启动）](#2-快速部署docker-一键启动)
- [3. 配置说明](#3-配置说明)
- [4. 数据库初始化](#4-数据库初始化)
- [5. 前端构建](#5-前端构建)
- [6. 爬虫 CDP 浏览器配置](#6-爬虫-cdp-浏览器配置)
- [7. LLM API 配置](#7-llm-api-配置)
- [8. 性能压测](#8-性能压测)
- [9. 运维监控](#9-运维监控)
- [10. 故障排查](#10-故障排查)
- [11. 生产安全清单](#11-生产安全清单)

---

## 1. 环境要求

### 最低配置

| 资源 | 最低 | 推荐 |
|------|------|------|
| CPU | 2 核 | 4 核 |
| 内存 | 4 GB | 8 GB |
| 磁盘 | 20 GB | 50 GB（含数据集） |
| 操作系统 | Linux x86_64 | Ubuntu 22.04 / Debian 12 |

### 软件依赖

| 软件 | 版本 | 用途 |
|------|------|------|
| Docker | 24.0+ | 容器运行时 |
| Docker Compose | 2.20+ | 多服务编排 |
| Node.js | 20+ | 前端构建（仅构建时需要） |
| pnpm | 9+ | 前端包管理（仅构建时需要） |

### 服务架构

```
                    ┌─────────────────────────────────┐
                    │         Docker Compose          │
                    │                                 │
   :8000 ────────── │  api (FastAPI + Uvicorn)        │
                    │    ├─ Postgres (pgvector)       │ :5432
                    │    ├─ Neo4j (5.x)               │ :7687/:7474
                    │    ├─ Redis (7-alpine)          │ :6379
                    │    └─ worker (ARQ async tasks)  │
                    │                                 │
   :5173 ────────── │  frontend (Vite dev / static)  │
                    └─────────────────────────────────┘
```

---

## 2. 快速部署（Docker 一键启动）

### 2.1 克隆项目

```bash
git clone https://github.com/PPy2205/zhigang-compass.git
cd zhigang-compass
```

### 2.2 配置环境变量

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`，填写以下必填项：

```ini
# 必须修改
SECRET_KEY=<your-random-secret-key>

# LLM API（JD/简历抽取必需）
LLM_API_KEY=<your-deepseek-api-key>
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat

# 数据库（Docker 内部地址，保持默认即可）
POSTGRES_DSN=postgresql+asyncpg://zhigang:zhigang@postgres:5432/zhigang
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
REDIS_URL=redis://redis:6379/0
```

### 2.3 构建前端

```bash
cd frontend
pnpm install
pnpm build          # 输出到 frontend/dist/
cd ..
```

### 2.4 启动全部服务

```bash
docker compose up -d
```

等待所有服务健康检查通过（约 30-60 秒）：

```bash
docker compose ps
```

输出应显示 5 个服务全部 `healthy`：

```
NAME               STATUS
zhigang-neo4j      Up (healthy)
zhigang-postgres   Up (healthy)
zhigang-redis      Up (healthy)
zhigang-api        Up (healthy)
zhigang-worker     Up (healthy)
```

### 2.5 验证部署

```bash
# 健康检查
curl http://localhost:8000/health

# API 文档
open http://localhost:8000/docs

# 前端页面
open http://localhost:8000/
```

---

## 3. 配置说明

### 3.1 环境变量一览

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_ENV` | `development` | 运行环境（`production` / `development`） |
| `SECRET_KEY` | `change-me-in-production` | JWT 签名密钥，**生产必须修改** |
| `POSTGRES_DSN` | — | PostgreSQL 连接串 |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt 连接地址 |
| `NEO4J_USER` | `neo4j` | Neo4j 用户名 |
| `NEO4J_PASSWORD` | `password` | Neo4j 密码 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接（限流/缓存） |
| `ARQ_REDIS_URL` | `redis://redis:6379/1` | ARQ 任务队列 Redis（独立 DB） |
| `LLM_API_KEY` | — | DeepSeek API Key |
| `LLM_BASE_URL` | `https://api.deepseek.com` | LLM API 基地址 |
| `LLM_MODEL` | `deepseek-chat` | LLM 模型名 |
| `JWT_PRIVATE_KEY_PATH` | `keys/private.pem` | JWT 私钥路径 |
| `JWT_PUBLIC_KEY_PATH` | `keys/public.pem` | JWT 公钥路径 |
| `FRONTEND_DIST_DIR` | `../frontend/dist` | 前端静态资源路径 |
| `BOSS_CDP_URL` | `http://127.0.0.1:9222` | 爬虫 CDP 浏览器地址 |
| `HTTP_PROXY` | （空） | 国际平台爬取代理 |

### 3.2 Docker Compose 服务端口

| 服务 | 容器端口 | 主机端口 | 说明 |
|------|---------|---------|------|
| api | 8000 | 8000 | FastAPI 后端 |
| postgres | 5432 | 5432 | pgvector 数据库 |
| neo4j | 7687/7474 | 7687/7474 | 图数据库 + Browser |
| redis | 6379 | 6379 | 缓存 + 限流 + 任务队列 |
| worker | — | — | ARQ 异步任务（无端口） |

### 3.3 数据卷

| 卷名 | 容器路径 | 说明 |
|------|---------|------|
| `pg_data` | `/var/lib/postgresql/data` | PostgreSQL 数据 |
| `neo4j_data` | `/data` | Neo4j 数据 |
| `neo4j_logs` | `/logs` | Neo4j 日志 |
| `redis_data` | `/data` | Redis 持久化 |

---

## 4. 数据库初始化

### 4.1 自动迁移

API 容器启动时自动执行 Alembic 迁移：

```bash
docker compose logs api | grep "alembic"
```

### 4.2 手动迁移

```bash
docker compose exec api uv run alembic upgrade head
```

### 4.3 初始化数据

首次部署后，导入黄金集和图谱数据：

```bash
# 导入黄金集
docker compose exec api uv run python scripts/import_golden_set.py

# 运行 ETL 管线（爬取 → 清洗 → 抽取 → 入图）
docker compose exec api uv run python scripts/run_etl.py
```

---

## 5. 前端构建

### 5.1 生产构建

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm build
```

构建产物输出到 `frontend/dist/`，Docker Compose 以只读方式挂载到 API 容器。

### 5.2 开发模式

```bash
# 启动后端服务
docker compose up -d postgres neo4j redis

# 启动前端开发服务器
cd frontend
pnpm dev   # http://localhost:5173
```

### 5.3 环境变量

前端只有一个环境变量 `VITE_API_TARGET`（开发模式后端地址），生产环境由 API 容器内 Uvicorn 直接提供静态资源服务，无需额外配置。

---

## 6. 爬虫 CDP 浏览器配置

国内平台（BOSS/智联/脉脉）通过 CDP 连接已登录的 Chrome 浏览器采集数据。

### 6.1 启动 CDP 浏览器

```bash
# 在有图形界面的机器上
google-chrome --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-profile \
  --no-first-run --no-default-browser-check
```

### 6.2 配置连接

在 `backend/.env` 中设置：

```ini
BOSS_CDP_URL=http://<browser-host>:9222
```

Docker 部署时，`<browser-host>` 改为浏览器所在机器的局域网 IP。

---

## 7. LLM API 配置

JD/简历的结构化抽取依赖 DeepSeek API。

### 7.1 获取 API Key

1. 访问 [DeepSeek 开放平台](https://platform.deepseek.com/)
2. 创建 API Key
3. 填入 `backend/.env`：

```ini
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

### 7.2 验证连通性

```bash
docker compose exec api uv run python -c "
from app.services.extraction.extractor import JDExtractor
import asyncio
result = asyncio.run(JDExtractor().extract('招聘Python开发工程师，精通Django'))
print(result)
"
```

---

## 8. 性能压测

### 8.1 运行压测

```bash
cd backend
mkdir -p reports/performance
uv run locust -f tests/performance/locustfile.py \
  --host http://localhost:8000 \
  --users 100 --spawn-rate 20 \
  --run-time 5m --headless \
  --csv=reports/performance/baseline
```

### 8.2 性能目标

| 指标 | 目标 |
|------|------|
| P95 响应时间 | < 2000ms |
| P50 响应时间 | < 500ms |
| 错误率 | < 1% |
| RPS | ≥ 50 |

详见 [性能压测指南](../backend/tests/performance/README.md)。

---

## 9. 运维监控

### 9.1 日志查看

```bash
# 全部服务日志
docker compose logs -f

# 单个服务
docker compose logs -f api
docker compose logs -f worker
```

### 9.2 健康检查

```bash
# API 健康状态
curl http://localhost:8000/health

# Docker 健康检查
docker compose ps
```

### 9.3 数据库管理

```bash
# PostgreSQL CLI
docker compose exec postgres psql -U zhigang -d zhigang

# Neo4j Browser
open http://localhost:7474
# 用户名: neo4j / 密码: password
```

### 9.4 Redis 管理

```bash
docker compose exec redis redis-cli
> INFO
> KEYS rate:*    # 查看限流键
> KEYS arq:*     # 查看任务队列
```

---

## 10. 故障排查

### 10.1 服务无法启动

```bash
# 检查容器状态
docker compose ps -a

# 查看启动日志
docker compose logs api | tail -50
```

常见原因：
- **端口冲突**：8000/5432/7687/6379 被占用 → 修改 `docker-compose.yml` 端口映射
- **.env 缺失**：`backend/.env` 文件不存在 → 执行 `cp backend/.env.example backend/.env`
- **SBERT 模型缺失**：容器启动时下载模型超时 → 挂载 `backend/models/` 目录

### 10.2 数据库连接失败

```bash
# 检查 Postgres 健康
docker compose exec postgres pg_isready -U zhigang

# 检查连接池
docker compose exec postgres psql -U zhigang -c "SELECT count(*) FROM pg_stat_activity;"
```

### 10.3 Neo4j 内存不足

`docker-compose.yml` 中 Neo4j 默认无内存限制。如果容器 OOM：

```yaml
neo4j:
  environment:
    NEO4J_server_memory_heap_initial__size: 512m
    NEO4J_server_memory_heap_max__size: 1G
```

### 10.4 Redis 限流误触发

压测时如果频繁收到 429 状态码：

```bash
# 查看限流键
docker compose exec redis redis-cli KEYS "rate:*"

# 临时清除限流
docker compose exec redis redis-cli FLUSHDB
```

或调大限流阈值（`backend/.env`）：

```ini
RATE_LIMIT_PER_MINUTE=10000
RATE_LIMIT_LLM_PER_MINUTE=1000
```

---

## 11. 生产安全清单

部署到生产环境前，逐项确认：

- [ ] `SECRET_KEY` 已修改为随机值（`openssl rand -hex 32`）
- [ ] Neo4j 密码已修改（非默认 `password`）
- [ ] Postgres 密码已修改（非默认 `zhigang`）
- [ ] `APP_ENV=production`
- [ ] `LLM_API_KEY` 已配置
- [ ] JWT 密钥对已重新生成（`openssl genrsa -out keys/private.pem 2048`）
- [ ] Docker 端口仅暴露必要端口（生产环境不暴露 5432/7687/6379）
- [ ] HTTPS 反向代理已配置（Nginx / Caddy）
- [ ] 数据备份策略已制定
- [ ] 日志轮转已配置

### HTTPS 反向代理示例（Nginx）

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SSE 长连接（简历解析进度流）
    location /api/v1/ {
        proxy_pass http://localhost:8000;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
```

---

## 附录：常用命令速查

| 操作 | 命令 |
|------|------|
| 启动全部服务 | `docker compose up -d` |
| 停止全部服务 | `docker compose down` |
| 停止并清除数据 | `docker compose down -v` |
| 重建 API 镜像 | `docker compose build api` |
| 查看日志 | `docker compose logs -f api` |
| 执行迁移 | `docker compose exec api uv run alembic upgrade head` |
| 进入 API 容器 | `docker compose exec api bash` |
| 运行测试 | `docker compose exec api uv run pytest` |
| 性能压测 | `cd backend && uv run locust -f tests/performance/locustfile.py --headless ...` |
| 生成 JWT 密钥 | `openssl genrsa -out backend/keys/private.pem 2048 && openssl rsa -in backend/keys/private.pem -pubout -out backend/keys/public.pem` |
