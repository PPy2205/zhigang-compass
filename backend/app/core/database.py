"""数据库连接管理：PostgreSQL (async) + Neo4j + Redis。

连接池参数从 settings 读取，适配 100 并发压测场景（设计文档 §13.3 P95 < 2s）。
"""

from neo4j import GraphDatabase
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool
from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool

from app.core.config import settings

# ---------- PostgreSQL (async) ----------
# pool_size=20 + max_overflow=30 = 最多 50 并发连接，适配 100 并发请求
# pool_pre_ping 检测断连自动重连，pool_recycle 定期回收防连接老化
engine = create_async_engine(
    settings.postgres_dsn,
    echo=settings.debug,
    poolclass=AsyncAdaptedQueuePool,
    pool_size=settings.pg_pool_size,
    max_overflow=settings.pg_max_overflow,
    pool_pre_ping=True,
    pool_recycle=settings.pg_pool_recycle,
)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        yield session


# ---------- Neo4j ----------
# max_connection_pool_size=50：连接复用，避免每个请求新建 TCP 连接
neo4j_driver = GraphDatabase.driver(
    settings.neo4j_uri,
    auth=(settings.neo4j_user, settings.neo4j_password),
    max_connection_pool_size=settings.neo4j_max_pool,
    connection_acquisition_timeout=30,
)


def get_neo4j():
    with neo4j_driver.session() as session:
        yield session


# ---------- Redis (async) ----------
# ConnectionPool 限制最大连接数，避免无限制创建连接压垮 Redis
redis_pool = ConnectionPool.from_url(
    settings.redis_url,
    max_connections=settings.redis_max_conn,
    decode_responses=True,
)
redis_client = Redis(connection_pool=redis_pool)


async def get_redis() -> Redis:
    return redis_client
