from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redisio import client as redis_client
from app.models import CandidateProfile
from app.services.scoring import theta_to_score

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/{specialization_code}", summary="Топ категории по итогам тестов (Redis)")
async def leaderboard(specialization_code: str, limit: int = 10,
                      db: AsyncSession = Depends(get_db)):
    try:
        top = await redis_client.zrevrange(
            f"leaderboard:{specialization_code}", 0, max(1, limit) - 1, withscores=True)
    except Exception:
        return {"items": [], "note": "Redis недоступен — рейтинг временно скрыт"}
    items = []
    for user_id, theta in top:
        profile = await db.get(CandidateProfile, user_id)
        if profile is None or not profile.is_public or profile.grade is None:
            continue
        first = (profile.full_name or "Аноним").split()[0]
        items.append({
            "rank": len(items) + 1,
            "name": first,
            "grade": profile.grade.value,
            "theta": round(theta, 2),
            "score": theta_to_score(theta),
        })
    return {"specialization": specialization_code, "items": items}
