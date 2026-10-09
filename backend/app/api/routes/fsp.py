import hashlib
import hmac
import json

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_candidate_profile
from app.core.config import settings
from app.core.db import get_db
from app.models import CandidateProfile
from app.services.scoring import fsp_index

router = APIRouter(prefix="/fsp", tags=["fsp"])

MOCK_REGISTRY = {
    "FSP-2026-0001": {
        "name": "Алексей Смирнов", "rating": 2847,
        "achievements": [
            {"kind": "tournament", "title": "Финал ICPC", "level": "international",
             "result": "4 место", "year": 2025},
            {"kind": "olympiad", "title": "Всероссийская олимпиада по программированию",
             "level": "national", "result": "2 место", "year": 2024},
            {"kind": "tournament", "title": "Кубок ФСП по алгоритмам",
             "level": "national", "result": "1 место", "year": 2026},
        ],
    },
    "FSP-2026-0002": {
        "name": "Мария Ковалёва", "rating": 2210,
        "achievements": [
            {"kind": "olympiad", "title": "Региональная олимпиада", "level": "regional",
             "result": "1 место", "year": 2025},
        ],
    },
    "FSP-2026-0003": {
        "name": "Дмитрий Орлов", "rating": 1950,
        "achievements": [
            {"kind": "event", "title": "Хакатон ФСП", "level": "regional",
             "result": "финалист", "year": 2026},
        ],
    },
}


def sign_record(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hmac.new(settings.secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()


@router.get("/registry/{fsp_id}", summary="История достижений участника ФСП (мок-реестр)")
async def registry(fsp_id: str):
    record = MOCK_REGISTRY.get(fsp_id)
    if record is None:
        return {"fsp_id": fsp_id, "exists": False, "achievements": [], "signature": None}
    return {"fsp_id": fsp_id, "exists": True, "name": record["name"],
            "rating": record["rating"], "achievements": record["achievements"],
            "signature": sign_record(record)}


@router.post("/link/{fsp_id}", summary="Связать профиль с ФСП ID")
async def link(fsp_id: str, candidate: CandidateProfile = Depends(get_candidate_profile),
               db: AsyncSession = Depends(get_db)):
    record = MOCK_REGISTRY.get(fsp_id)
    if record is None:
        return {"linked": False,
                "note": "История ФСП не найдена — категория определяется только тестом"}
    candidate.fsp_id = fsp_id
    candidate.fsp_history = record["achievements"]
    return {
        "linked": True,
        "name": record["name"],
        "rating": record["rating"],
        "achievements": record["achievements"],
        "fsp_index": round(fsp_index(candidate.fsp_history), 3),
        "signature": sign_record(record),
    }
