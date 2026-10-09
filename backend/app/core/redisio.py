from redis import asyncio as aioredis

from app.core.config import settings

client = aioredis.from_url(
    settings.redis_url, socket_connect_timeout=0.5, socket_timeout=0.5,
    decode_responses=True,
)
