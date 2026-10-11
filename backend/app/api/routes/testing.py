from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_candidate_profile, get_employer_profile
from app.core.db import get_db
from app.core.config import settings
from app.models import (
    CandidateCategory,
    CandidateProfile,
    Grade,
    Specialization,
    TestBlueprint,
    TestSession,
    TestStatus,
)
from app.schemas import AnswerIn, SurveyIn
from app.services.testing import engine
from app.services.testing.scenarios import SCENARIOS

router = APIRouter(tags=["testing"])

@router.post("/testing/specializations", status_code=201,
             summary="Создать своё направление (вписанное работодателем) + банк заданий")
async def create_specialization(name: str, employer=Depends(get_employer_profile),
                                db=Depends(get_db)):
    from app.models import ItemTemplate
    from app.services.testing.scenarios import universal_scenario, build_bank_items
    code = name.lower().strip()[:32]
    if not code:
        raise HTTPException(422, "Пустое название направления")
    exists = await db.get(Specialization, code)
    if exists:
        return {"code": exists.code, "name": exists.name, "created": False}
    sc = universal_scenario(name)
    db.add(Specialization(code=sc.spec_code, name=sc.spec_name,
                          description=sc.spec_description, survey_options=[]))
    for item in build_bank_items(sc):
        db.add(ItemTemplate(**item))
    await db.flush()
    return {"code": code, "name": name, "created": True}


@router.get("/skills", summary="Справочник навыков (алфавитный)")
async def skills_catalog():
    from app.services.testing.scenarios import SKILLS_CATALOG
    return SKILLS_CATALOG


@router.get("/testing/specializations", summary="Справочник специализаций (для опроса)")
async def list_specializations(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Specialization))).scalars().all()
    stack_by_code = {sc.spec_code: sc.stack_tags for sc in SCENARIOS}
    return [
        {
            "code": s.code,
            "name": s.name,
            "description": s.description,
            "survey_options": s.survey_options,
            "stack_tags": stack_by_code.get(s.code, []),
        }
        for s in rows
    ]

@router.post("/testing/survey", summary="Опрос: специализация + заявленный уровень, старт теста")
async def survey(body: SurveyIn, candidate=Depends(get_candidate_profile), db=Depends(get_db)):
    spec = await db.get(Specialization, body.specialization_code)
    if spec is None:
        raise HTTPException(404, "Неизвестная специализация")

    is_initial = candidate.grade is None
    session = await engine.start_session(
        db, candidate, body.specialization_code, Grade(body.target_grade), is_initial,
        code_language=body.code_language,
    )
    first = await engine.next_item(db, session)
    return {
        "session_id": str(session.id),
        "is_initial": is_initial,
        "first_item": first,
        "target_items": settings.cat_target_items,
        "note": "Отвечайте на задания; система адаптирует сложность под вас",
    }

@router.post("/testing/answer", summary="Ответ на задание; возвращает следующее или итог")
async def answer(body: AnswerIn, candidate=Depends(get_candidate_profile),
                 db=Depends(get_db)):
    session = (await db.execute(
        select(TestSession).where(
            TestSession.candidate_id == candidate.user_id,
            TestSession.status == TestStatus.in_progress,
        ).order_by(TestSession.started_at.desc())
    )).scalars().first()
    if session is None:
        raise HTTPException(404, "Активная тест-сессия не найдена")

    try:
        result = await engine.submit_answer(
            db, session, item_id=body.item_id, payload=body.payload(),
            time_spent_ms=body.time_spent_ms, away_ms=body.away_ms,
            tab_switches=body.tab_switches,
        )
    except ValueError as e:
        raise HTTPException(409 if "уже" in str(e) else 400, str(e))
    return result
@router.post("/testing/start-by-invitation/{invitation_id}",
             summary="Тест по авторскому набору работодателя (из приглашения)")
async def start_by_invitation(invitation_id: str, target_grade: str = "junior",
                              candidate=Depends(get_candidate_profile), db=Depends(get_db)):
    from app.models import Invitation
    inv = await db.get(Invitation, invitation_id)
    if inv is None or inv.candidate_id != candidate.user_id:
        raise HTTPException(404, "Приглашение не найдено")
    if inv.blueprint_id is None:
        raise HTTPException(422, "У этого приглашения нет авторского теста")

    bp = await db.get(TestBlueprint, inv.blueprint_id)
    if bp is None or bp.status != "published":
        raise HTTPException(404, "Авторский тест не найден")
    try:
        grade = Grade(target_grade)
    except ValueError:
        raise HTTPException(422, "Неизвестный уровень")
    session = await engine.start_session(
        db, candidate, bp.specialization_code, grade, is_initial=False,
        blueprint_id=inv.blueprint_id, code_language=bp.code_language,
    )
    first = await engine.next_item(db, session)
    return {
        "session_id": str(session.id),
        "blueprint_id": inv.blueprint_id,
        "first_item": first,
        "note": "Тест составлен работодателем по его потребности",
    }

@router.get("/testing/history", summary="История прохождений тестов по направлениям")
async def test_history(candidate=Depends(get_candidate_profile), db=Depends(get_db)):
    rows = (await db.execute(
        select(TestSession)
        .where(TestSession.candidate_id == candidate.user_id,
               TestSession.status == TestStatus.completed)
        .order_by(TestSession.finished_at)
    )).scalars().all()
    from app.models import Specialization
    spec_names = {s.code: s.name for s in (await db.execute(select(Specialization))).scalars().all()}
    return [{**g, "specialization": spec_names.get(g["specialization"], g["specialization"])}
            for g in engine.sessions_history(rows)]


@router.get("/testing/status", summary="Текущий статус: категории, уровни, история")
async def status(candidate=Depends(get_candidate_profile), db=Depends(get_db)):
    from app.models import Specialization
    from app.services.scoring import category_ru
    spec_names = {s.code: s.name for s in (await db.execute(select(Specialization))).scalars().all()}
    cats = (await db.execute(
        select(CandidateCategory).where(CandidateCategory.candidate_id == candidate.user_id)
    )).scalars().all()
    return {
        "specialization": candidate.specialization_code,
        "grade": candidate.grade.value if candidate.grade else None,
        "category": (
            category_ru(spec_names.get(candidate.specialization_code, candidate.specialization_code),
                        candidate.grade.value)
            if candidate.grade and candidate.specialization_code else None
        ),
        "categories": [
            {"specialization": c.specialization_code, "grade": c.grade.value,
             "category": category_ru(spec_names.get(c.specialization_code, c.specialization_code), c.grade.value),
             "theta": c.theta}
            for c in cats
        ],
        "theta": candidate.theta,
        "theta_se": candidate.theta_se,
        "theta_history": candidate.theta_history,
        "grade_change_cooldown_days": settings.grade_change_cooldown_days,
        "last_grade_change_at": (
            candidate.last_grade_change_at.isoformat() if candidate.last_grade_change_at else None
        ),
    }


DEMO_TARGET_ITEMS = 3
_DEMO_STORE: dict[str, dict] = {}


class DemoAnswerIn(BaseModel):
    token: str
    item_id: str
    choice: int | None = None
    value: str | None = None


async def _demo_issue(db: AsyncSession, state: dict) -> dict | None:
    from app.models import ItemTemplate
    rows = (await db.execute(
        select(ItemTemplate).where(
            ItemTemplate.specialization_code == state["spec"],
            ItemTemplate.is_active.is_(True),
        )
    )).scalars().all()
    pool = [
        r for r in rows
        if str(r.id) not in state["variants"] and (r.template_params or {}).get("generator")
    ]
    if not pool:
        return None
    best, info = None, -1.0
    for r in pool:
        cur = float(engine.irt_info(state["theta"], r.a, r.b, r.c))
        if cur > info:
            best, info = r, cur
    import random as _random
    gen = engine.GENERATORS[best.template_params["generator"]]
    params = dict(best.template_params.get("params", {}))
    params["language"] = state.get("language") or "python"
    variant = gen(_random.Random(), params)
    state["variants"][str(best.id)] = {
        "variant": variant, "abc": (best.a, best.b, best.c),
    }
    return {
        "id": str(best.id), "title": best.title,
        "body": variant["body"], "options": variant.get("options"),
        "answer_type": variant.get("answer_type"),
    }


@router.post("/demo/quiz/start", summary="Публичное демо CAT: 3 адаптивных задания без регистрации")
async def demo_quiz_start(spec: str = "backend", language: str = "python",
                          db: AsyncSession = Depends(get_db)):
    import secrets
    if language not in engine.CODE_LANGUAGES:
        language = "python"
    token = secrets.token_urlsafe(12)
    state = {"spec": spec, "language": language, "theta": 0.0, "asked": 0,
             "history": [], "variants": {}}
    item = await _demo_issue(db, state)
    if item is None:
        raise HTTPException(404, "Для этого направления пока нет заданий")
    if len(_DEMO_STORE) > 5000:
        _DEMO_STORE.clear()
    _DEMO_STORE[token] = state
    return {"token": token, "item": item, "target_items": DEMO_TARGET_ITEMS,
            "note": "Сложность подбирается под ваш уровень прямо во время демо"}


@router.post("/demo/quiz/answer", summary="Ответ в демо-тесте; сервер адаптирует следующее задание")
async def demo_quiz_answer(body: DemoAnswerIn, db: AsyncSession = Depends(get_db)):
    state = _DEMO_STORE.get(body.token)
    if state is None or body.item_id not in state["variants"]:
        raise HTTPException(410, "Демо-сессия истекла — начните заново")
    stored = state["variants"].pop(body.item_id)
    variant, abc = stored["variant"], stored["abc"]

    if variant.get("answer_type") == "choice":
        correct = body.choice == variant.get("answer")
    else:
        correct = str(body.value or "").strip() == str(variant.get("answer", "")).strip()

    a, b, c = abc
    state["history"].append((a, b, c, correct))
    state["theta"] = engine.estimate_theta_eap(state["history"])
    state["asked"] += 1

    payload = {"correct": correct, "answer": variant.get("answer"),
               "theta": round(state["theta"], 2)}
    if state["asked"] >= DEMO_TARGET_ITEMS:
        from app.services.scoring import theta_to_score
        payload["finished"] = True
        payload["score"] = theta_to_score(state["theta"])
        _DEMO_STORE.pop(body.token, None)
    else:
        payload["next_item"] = await _demo_issue(db, state)
    return payload
