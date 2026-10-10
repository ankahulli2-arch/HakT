from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import Base, DbSessionMiddleware, engine
from app.core.ratelimit import RateLimitMiddleware
from app.api.routes import (
    admin,
    auth,
    employer_tests,
    fsp,
    health,
    interaction,
    leaderboard,
    matching,
    profiles,
    testing,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    from app.api.routes.admin import restore_demo_media
    restore_demo_media()
    yield

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        description=(
            "Платформа подбора ИТ-специалистов с обратной механикой: "
            "кандидат тестируется и попадает в категорию, работодатель "
            "сам выходит на кандидата с приглашением и уровнем зарплаты."
        ),
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(DbSessionMiddleware)
    app.add_middleware(RateLimitMiddleware)

    for r in (health, auth, testing, profiles, matching, interaction, fsp,
              employer_tests, leaderboard, admin):
        app.include_router(r.router, prefix="/api")

    return app

app = create_app()
