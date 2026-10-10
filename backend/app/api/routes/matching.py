import time

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_employer_profile
from app.core.db import get_db
from app.models import EmployerNeed, Grade
from app.schemas import NeedIn
from app.services import scoring

router = APIRouter(tags=["matching"])

@router.post("/matching/need", summary="Описать потребность → сохранить и получить подборку")
async def create_need(body: NeedIn, employer=Depends(get_employer_profile),
                      db=Depends(get_db)):
    started = time.perf_counter()
    parsed = await scoring.parse_need(db, body.raw_text)

    need = EmployerNeed(
        employer_id=employer.user_id,
        raw_text=body.raw_text,
        specialization_code=body.specialization_code or parsed["specialization_code"],
        min_grade=Grade(body.min_grade) if body.min_grade else parsed["min_grade"],
        stack=body.stack or parsed["stack"],
    )
    db.add(need)
    await db.flush()

    shortlist = await scoring.build_shortlist(
        db, need, limit=20, only_fsp=body.only_fsp, blind=employer.blind_mode,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    return {
        "need_id": str(need.id),
        "parsed": {
            "specialization_code": need.specialization_code,
            "min_grade": need.min_grade.value if need.min_grade else None,
            "stack": need.stack,
        },
        "elapsed_ms": elapsed_ms,
        "items": shortlist,
    }

@router.post("/matching/search", summary="Поиск по банку кандидатов с фильтрами")
async def search(body: NeedIn, employer=Depends(get_employer_profile), db=Depends(get_db)):
    started = time.perf_counter()
    parsed = await scoring.parse_need(db, body.raw_text) if body.raw_text else {}
    need = EmployerNeed(
        employer_id=employer.user_id,
        raw_text=body.raw_text,
        specialization_code=body.specialization_code or parsed.get("specialization_code"),
        min_grade=Grade(body.min_grade) if body.min_grade else parsed.get("min_grade"),
        stack=body.stack or parsed.get("stack", []),
    )
    shortlist = await scoring.build_shortlist(db, need, limit=50, only_fsp=body.only_fsp,
                                              blind=employer.blind_mode)
    return {
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "items": shortlist,
    }
