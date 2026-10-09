import time
from collections import deque, defaultdict

from starlette.responses import JSONResponse

from app.core.redisio import client

AUTH_LIMIT = 20
BASE_LIMIT = 240


class RateLimitMiddleware:
    def __init__(self, app):
        self.app = app
        self.auth_hits: dict[str, deque] = defaultdict(deque)
        self.base_hits: dict[str, deque] = defaultdict(deque)

    def _hit_local(self, bucket: dict, ip: str, limit: int) -> bool:
        now = time.monotonic()
        q = bucket[ip]
        while q and q[0] < now - 60:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True

    async def _hit_redis(self, bucket: str, ip: str, limit: int) -> bool:
        now = time.time()
        key = f"ratelimit:{bucket}:{ip}"
        pipe = client.pipeline()
        pipe.zremrangebyscore(key, 0, now - 60)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, 60)
        _, count, _, _ = await pipe.execute()
        return count < limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        ip = (scope.get("client") or ("?",))[0]
        path = scope.get("path", "")
        if path.startswith("/api/auth"):
            bucket, limit = "auth", AUTH_LIMIT
        else:
            bucket, limit = "base", BASE_LIMIT
        try:
            ok = await self._hit_redis(bucket, ip, limit)
        except Exception:
            ok = self._hit_local(
                self.auth_hits if bucket == "auth" else self.base_hits, ip, limit)
        if not ok:
            await JSONResponse({"detail": f"Слишком много запросов, лимит {limit}/мин"},
                               status_code=429)(scope, receive, send)
            return
        await self.app(scope, receive, send)
