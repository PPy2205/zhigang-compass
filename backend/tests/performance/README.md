# 性能压测指南（TE-M5-01）

> 设计文档 §13.3：100 并发下 P95 < 2s

## 环境要求

- Docker Compose 全部服务启动（api + postgres + neo4j + redis + worker）
- Python 3.13+（locust 已在 dev 依赖中）
- 至少 2 核 CPU / 4GB 内存

## 快速开始

### 1. 启动后端服务

```bash
docker compose up -d
```

### 2. 运行基线压测（5 分钟，100 用户）

```bash
cd backend

# 创建报告目录
mkdir -p reports/performance

# 无界面运行（推荐 CI/自动化）
uv run locust -f tests/performance/locustfile.py \
  --host http://localhost:8000 \
  --users 100 \
  --spawn-rate 20 \
  --run-time 5m \
  --headless \
  --csv=reports/performance/baseline
```

### 3. Web UI 模式（交互式调试）

```bash
cd backend
uv run locust -f tests/performance/locustfile.py --host http://localhost:8000
```

访问 http://localhost:8089 设置并发数和持续时间。

## 压测场景

| 场景 | 权重 | 接口 | 说明 |
|------|------|------|------|
| 图谱全景 | 30% | GET /graph/panorama | 首页加载，最高频 |
| 技能搜索 | 25% | GET /graph/search?q=xxx | 用户探索行为 |
| 岗位详情 | 15% | GET /graph/position/{id} + /skills | 岗位详情页 |
| 匹配推荐 | 15% | POST /match/recommend + 轮询 | 核心功能，含 LLM |
| 演化看板 | 10% | GET /evolution/versions + trends + signals | 演化页面 |
| 认证流程 | 5% | GET /auth/me | 低频操作 |

## 性能指标

### 目标阈值（设计文档 §13.3）

| 指标 | 目标 | 说明 |
|------|------|------|
| P95 响应时间 | < 2000ms | 所有接口 |
| P50 响应时间 | < 500ms | 核心读接口 |
| 错误率 | < 1% | 含 4xx/5xx |
| RPS | ≥ 50 | 100 并发下 |

### 分接口阈值

| 接口类型 | P95 目标 | 说明 |
|----------|----------|------|
| 简单读接口 | < 500ms | 如 auth/me、evolution/versions |
| 图谱查询 | < 1000ms | 如 graph/panorama、graph/search |
| 匹配计算 | < 2000ms | 如 match/recommend（含 LLM） |
| 异步任务提交 | < 500ms | 202 立即返回 |

## 标签过滤运行

运行特定场景的压测：

```bash
# 只跑图谱相关
uv run locust -f tests/performance/locustfile.py --tags graph --headless ...

# 只跑匹配（含 LLM）
uv run locust -f tests/performance/locustfile.py --tags match llm --headless ...

# 排除 LLM 接口（纯基线性能）
uv run locust -f tests/performance/locustfile.py --exclude-tags llm --headless ...
```

## 报告解读

### CSV 输出文件

- `baseline_stats.csv` — 每个请求的统计数据
- `baseline_stats_history.csv` — 每秒的历史数据（用于绘图）
- `baseline_failures.csv` — 失败请求详情

### 关键指标解读

```
# 查看 P95
grep ",GET graph/panorama," baseline_stats.csv | awk -F, '{print "P95:", $9 "ms"}'

# 查看错误率
grep ",GET graph/search," baseline_stats.csv | awk -F, '{print "Error%:", $6}'
```

## 常见问题

### 1. 压测时 Redis 限流触发

TE-M4-03 实现的令牌桶限流（100 req/min 普通 / 10 req/min LLM）会在高压下触发 429。
如果要测试接口本身的性能，可临时调大限流阈值或跳过限流中间件。

### 2. Neo4j 连接池耗尽

压测前检查 Neo4j 配置：

```cypher
CALL dbms.listConnections() YIELD connectionId, connector
```

必要时调大 `dbms.connector.bolt.thread_pool_max_size`。

### 3. 数据库连接池耗尽

检查 Postgres 连接数：

```sql
SELECT count(*) FROM pg_stat_activity;
```

必要时调大 `DB_POOL_SIZE` 环境变量。

## 性能优化建议

如压测不达标，按以下优先级优化：

1. **缓存热点接口**：Redis 缓存 graph/panorama、graph/search 等高频读接口
2. **数据库索引优化**：检查慢查询，添加缺失的索引
3. **连接池调优**：Postgres / Neo4j / Redis 连接池大小
4. **异步任务优化**：匹配推荐等重操作已异步，检查 worker 消费速度
5. **LLM 批处理**：LLM 请求批量合并，减少 API 调用次数
