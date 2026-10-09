from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db

router = APIRouter(tags=["health"])

@router.get("/health", summary="Проверка живости сервиса")
async def health() -> dict:
    return {"status": "ok"}

@router.get("/health/db", summary="Проверка соединения с БД")
async def health_db(db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(text("SELECT 1"))
    return {"status": "ok", "db": result.scalar() == 1}
