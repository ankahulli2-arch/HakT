from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass
class DbSessionMiddleware:
    """Сессия БД на запрос; commit до отправки ответа.

    Это устраняет гонку: следующий запрос клиента не может прочитаться
    раньше, чем закоммичен предыдущий.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        async with SessionLocal() as session:
            scope.setdefault("state", {})["db"] = session

            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    await session.commit()
                await send(message)

            try:
                await self.app(scope, receive, send_wrapper)
            except Exception:
                await session.rollback()
                raise

async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    yield request.state.db

