import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_employer_profile
from app.core.db import get_db
from app.models import TestBlueprint
from app.services.testing import blueprint as bp_service
from app.services.testing.engine import GENERATORS

router = APIRouter(prefix="/employer/tests", tags=["employer-tests"])

class DraftIn(BaseModel):
    specialization_code: str
    raw_text: str = ""
    use_web: bool = True
    vacancy_id: str | None = None
    code_language: str = Field(default="python",
                               pattern=r"^(python|javascript|c\+\+|c#|java)$")

class ItemsIn(BaseModel):
    items: list[dict] = Field(min_length=1)

    @field_validator("items")
    @classmethod
    def valid_entries(cls, v):
        for e in v:
            if e.get("source") not in ("bank", "custom") or not e.get("ref_id"):
                raise ValueError("каждый пункт теста: source bank|custom и ref_id")
        return v

class CustomItemIn(BaseModel):
    title: str
    body: str
    options: list[str] = []
    correct: str

@router.post("/draft", status_code=201, summary="Авто-черновик: серчинг навыков + сборка теста")
async def create_draft(body: DraftIn, employer=Depends(get_employer_profile),
                       db=Depends(get_db)):
    try:
        bp = await bp_service.make_draft(
            db, employer.user_id, body.specialization_code, body.raw_text,
            use_web=body.use_web, vacancy_id=body.vacancy_id,
            code_language=body.code_language,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {
        "blueprint_id": str(bp.id),
        "status": bp.status,
        "researched_skills": bp.researched_skills,
        "code_language": bp.code_language,
        "items": bp.items_json,
        "note": "Черновик можно оставить как есть, убрать/добавить вопросы "
                "или заменить весь тест своими вопросами",
    }

@router.get("", summary="Мои черновики и опубликованные тесты")
async def my_blueprints(employer=Depends(get_employer_profile), db=Depends(get_db)):
    rows = (await db.execute(
        select(TestBlueprint).where(TestBlueprint.employer_id == employer.user_id)
        .order_by(TestBlueprint.created_at.desc())
    )).scalars().all()
    return [
        {
            "id": str(b.id), "title": b.title, "status": b.status,
            "specialization_code": b.specialization_code,
            "vacancy_id": str(b.vacancy_id) if b.vacancy_id else None,
            "code_language": b.code_language,
            "researched_skills": b.researched_skills,
            "items_count": len(b.items_json),
        }
        for b in rows
    ]

async def _own_blueprint(db, employer, blueprint_id: str) -> TestBlueprint:
    bp = await db.get(TestBlueprint, blueprint_id)
    if bp is None or bp.employer_id != employer.user_id:
        raise HTTPException(404, "Черновик не найден")
    return bp


@router.get("/{blueprint_id}", summary="Просмотр черновика (с образцом каждого вопроса)")
async def get_blueprint(blueprint_id: str, employer=Depends(get_employer_profile),
                        db=Depends(get_db)):
    bp = await _own_blueprint(db, employer, blueprint_id)
    items = []
    for e in bp.items_json:
        item = dict(e)
        if e["source"] == "bank":
            gen = GENERATORS[e["template_params"]["generator"]]
            params = dict(e["template_params"].get("params") or {})
            params["language"] = bp.code_language or "python"
            sample = gen(random.Random(f"{bp.id}:{e.get('ref_id')}"), params)
            answer = None
            if sample.get("answer_type") == "choice" and sample.get("options"):
                answer = sample["options"][sample.get("answer")]
            else:
                answer = sample.get("answer")
            item["sample"] = {"body": sample["body"], "options": sample.get("options"),
                              "answer": str(answer) if answer is not None else None}
        else:
            item["sample"] = {"body": e["body"], "options": e.get("options"),
                              "answer": e.get("correct")}
        items.append(item)
    return {"id": str(bp.id), "title": bp.title,
            "status": "опубликован" if bp.status == "published" else "черновик",
            "specialization_code": bp.specialization_code,
            "vacancy_id": str(bp.vacancy_id) if bp.vacancy_id else None,
            "researched_skills": bp.researched_skills, "items": items}

@router.put("/{blueprint_id}/items", summary="Заменить состав теста целиком")
async def put_items(blueprint_id: str, body: ItemsIn,
                    employer=Depends(get_employer_profile), db=Depends(get_db)):
    bp = await _own_blueprint(db, employer, blueprint_id)
    bp = await bp_service.replace_items(db, bp, body.items)
    return {"id": str(bp.id), "items_count": len(bp.items_json)}

@router.post("/{blueprint_id}/items", status_code=201,
             summary="Добавить свой вопрос с ответом")
async def add_item(blueprint_id: str, body: CustomItemIn,
                   employer=Depends(get_employer_profile), db=Depends(get_db)):
    bp = await _own_blueprint(db, employer, blueprint_id)
    if body.correct not in body.options and body.options:
        raise HTTPException(422, "correct должен совпадать с одним из options")
    entry = await bp_service.add_custom_item(
        db, bp, body.title, body.body, body.options, body.correct,
    )
    return entry

@router.delete("/{blueprint_id}/items/{item_ref}", summary="Убрать задание из теста")
async def remove_item(blueprint_id: str, item_ref: str,
                      employer=Depends(get_employer_profile), db=Depends(get_db)):
    bp = await _own_blueprint(db, employer, blueprint_id)
    bp.items_json = [e for e in bp.items_json if e.get("ref_id") != item_ref]
    await db.flush()
    return {"id": str(bp.id), "items_count": len(bp.items_json)}

@router.post("/{blueprint_id}/publish", summary="Опубликовать тест (прикрепляется к приглашениям)")
async def publish(blueprint_id: str, employer=Depends(get_employer_profile),
                  db=Depends(get_db)):
    bp = await _own_blueprint(db, employer, blueprint_id)
    if not bp.items_json:
        raise HTTPException(422, "Пустой тест публиковать нельзя")
    bp = await bp_service.publish(db, bp)
    return {"id": str(bp.id), "status": bp.status,
            "note": "Теперь при приглашении можно указать blueprint_id — "
                    "кандидат будет тестироваться по вашему набору заданий"}
