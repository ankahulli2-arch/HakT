import math
import time
from datetime import datetime, timedelta, timezone

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_candidate_profile, get_employer_profile
from app.core.db import get_db
from app.models import (
    Application,
    CandidateCategory,
    CandidateProfile,
    EmployerNeed,
    EmployerProfile,
    Grade,
    InteractionStatus,
    Invitation,
    Microtask,
    MicrotaskStatus,
    Specialization,
    TestBlueprint,
    TestSession,
    TestStatus,
    Vacancy,
)
from app.schemas import InvitationIn, VacancyIn, VacancyOut
from app.services.scoring import build_shortlist, category_ru, final_score
from app.services.testing import engine

INVITE_TTL_DAYS = 14


async def expire_stale_invitations(db: AsyncSession) -> None:
    for inv in (await db.execute(
        select(Invitation).where(
            Invitation.status == InteractionStatus.sent,
            Invitation.created_at < datetime.now(timezone.utc) - timedelta(days=INVITE_TTL_DAYS),
        )
    )).scalars().all():
        inv.status = InteractionStatus.expired


STATUS_RU = {
    InteractionStatus.sent: "отправлено",
    InteractionStatus.viewed: "просмотрено",
    InteractionStatus.accepted: "принято",
    InteractionStatus.declined: "отклонено",
    InteractionStatus.expired: "истекло",
}

router = APIRouter(tags=["interaction"])

@router.post("/vacancies", response_model=VacancyOut, status_code=201)
async def create_vacancy(body: VacancyIn, employer=Depends(get_employer_profile),
                         db=Depends(get_db)):
    if body.salary_min > body.salary_max:
        raise HTTPException(422, "salary_min не может быть больше salary_max")
    data = body.model_dump()
    data["min_grade"] = Grade(body.min_grade)
    v = Vacancy(employer_id=employer.user_id, **data)
    db.add(v)
    await db.flush()
    return _vacancy_out(v, employer.company_name)

def _vacancy_out(v: Vacancy, company: str) -> VacancyOut:
    return VacancyOut(
        id=str(v.id), title=v.title, description=v.description,
        specialization_code=v.specialization_code, min_grade=v.min_grade.value,
        stack=v.stack, salary_min=v.salary_min, salary_max=v.salary_max,
        company_name=company, is_active=v.is_active, code_language=v.code_language,
    )

@router.get("/vacancies", summary="Публичный список активных вакансий (для кандидатов)")
async def list_vacancies(db=Depends(get_db), specialization_code: str | None = None):
    q = select(Vacancy).where(Vacancy.is_active.is_(True))
    if specialization_code:
        q = q.where(Vacancy.specialization_code == specialization_code)
    vacancies = (await db.execute(q.order_by(Vacancy.created_at.desc()))).scalars().all()
    companies = {}
    for v in vacancies:
        if v.employer_id not in companies:
            companies[v.employer_id] = (await db.get(EmployerProfile, v.employer_id)).company_name
    return [_vacancy_out(v, companies[v.employer_id]) for v in vacancies]

async def _own_vacancy(db, employer, vacancy_id: str):
    v = await db.get(Vacancy, vacancy_id)
    if v is None or v.employer_id != employer.user_id:
        raise HTTPException(404, "Вакансия не найдена")
    return v


async def _own_invitation(db, profile, invitation_id: str):
    inv = await db.get(Invitation, invitation_id)
    if inv is None or inv.candidate_id != profile.user_id:
        raise HTTPException(404, "Приглашение не найдено")
    return inv


async def _own_microtask(db, profile, microtask_id: str):
    mt = await db.get(Microtask, microtask_id)
    if mt is None or mt.candidate_id != profile.user_id:
        raise HTTPException(404, "Задача не найдена")
    return mt


@router.delete("/vacancies/{vacancy_id}", summary="Снять свою вакансию")
async def delete_vacancy(vacancy_id: str, employer=Depends(get_employer_profile),
                         db=Depends(get_db)):
    v = await _own_vacancy(db, employer, vacancy_id)
    v.is_active = False
    return {"id": vacancy_id, "is_active": False}


@router.get("/employer/vacancies", summary="Мои вакансии с входящими откликами")
async def my_vacancies(employer=Depends(get_employer_profile), db=Depends(get_db)):
    vacancies = (await db.execute(
        select(Vacancy).where(Vacancy.employer_id == employer.user_id)
        .order_by(Vacancy.created_at.desc())
    )).scalars().all()
    out = []
    for v in vacancies:
        apps = (await db.execute(
            select(Application).where(Application.vacancy_id == v.id)
        )).scalars().all()
        out.append({
            **_vacancy_out(v, employer.company_name).model_dump(),
            "applications": [
                {
                    "id": str(a.id), "candidate_id": str(a.candidate_id),
                    "cover_letter": a.cover_letter, "status": a.status.value,
                    "candidate_contacts": (
                        (await db.get(CandidateProfile, a.candidate_id)).contacts
                        if a.contact_revealed_at is not None else None
                    ),
                }
                for a in apps
            ],
        })
    return out


@router.post("/invitations", status_code=201, summary="Пригласить кандидата (обратная механика)")
async def invite(body: InvitationIn, employer=Depends(get_employer_profile),
                 db=Depends(get_db)):
    candidate = await db.get(CandidateProfile, body.candidate_id)
    if candidate is None or not candidate.is_public:
        raise HTTPException(404, "Кандидат не найден")
    if not candidate.consent_data_processing:
        raise HTTPException(403, "У кандидата нет согласия на обработку данных")
    if body.salary_min > body.salary_max:
        raise HTTPException(422, "salary_min не может быть больше salary_max")
    if body.vacancy_id is not None:
        await _own_vacancy(db, employer, str(body.vacancy_id))
    if body.blueprint_id is not None:
        bp = await db.get(TestBlueprint, body.blueprint_id)
        if bp is None or bp.employer_id != employer.user_id or bp.status != "published":
            raise HTTPException(404, "Опубликованный тест не найден")

    inv = Invitation(
        employer_id=employer.user_id,
        candidate_id=body.candidate_id,
        vacancy_id=body.vacancy_id,
        blueprint_id=body.blueprint_id,
        message=body.message,
        salary_min=body.salary_min,
        salary_max=body.salary_max,
    )
    db.add(inv)
    await db.flush()
    return {"id": str(inv.id), "status": inv.status.value}

@router.get("/candidate/invitations", summary="Входящие приглашения кандидата")
async def candidate_invitations(profile=Depends(get_candidate_profile), db=Depends(get_db)):
    await expire_stale_invitations(db)
    rows = (await db.execute(
        select(Invitation).where(Invitation.candidate_id == profile.user_id)
        .order_by(Invitation.created_at.desc())
    )).scalars().all()
    for inv in rows:
        if inv.status == InteractionStatus.sent:
            inv.status = InteractionStatus.viewed
    out = []
    for inv in rows:
        emp = await db.get(EmployerProfile, inv.employer_id)
        out.append({
            "id": str(inv.id),
            "company_name": emp.company_name,
            "message": inv.message,
            "salary_min": inv.salary_min,
            "salary_max": inv.salary_max,
            "status": inv.status.value,
            "status_ru": STATUS_RU[inv.status],
            "vacancy_id": str(inv.vacancy_id) if inv.vacancy_id else None,
            "blueprint_id": str(inv.blueprint_id) if inv.blueprint_id else None,
            "created_at": inv.created_at.isoformat(),
        })
    return out

@router.post("/candidate/invitations/{invitation_id}/decide",
             summary="Принять или отклонить приглашение")
async def decide_invitation(invitation_id: str, accept: bool,
                            profile=Depends(get_candidate_profile), db=Depends(get_db)):
    inv = await _own_invitation(db, profile, invitation_id)
    if inv.status not in (InteractionStatus.sent, InteractionStatus.viewed):
        raise HTTPException(409, "Решение уже принято")
    inv.status = InteractionStatus.accepted if accept else InteractionStatus.declined
    inv.decided_at = datetime.now(timezone.utc)
    if accept:

        inv.contact_revealed_at = datetime.now(timezone.utc)
    return {"id": str(inv.id), "status": inv.status.value,
            "contact_revealed": accept}

@router.get("/employer/invitations", summary="Мои приглашения и их статусы")
async def employer_invitations(employer=Depends(get_employer_profile), db=Depends(get_db)):
    await expire_stale_invitations(db)
    rows = (await db.execute(
        select(Invitation).where(Invitation.employer_id == employer.user_id)
        .order_by(Invitation.created_at.desc())
    )).scalars().all()
    out = []
    for inv in rows:
        cand = await db.get(CandidateProfile, inv.candidate_id)
        revealed = inv.contact_revealed_at is not None
        out.append({
            "id": str(inv.id),
            "candidate_id": str(inv.candidate_id),
            "candidate_category": f"{cand.specialization_code} · {cand.grade.value}"
            if cand.grade else None,
            "message": inv.message,
            "salary_min": inv.salary_min, "salary_max": inv.salary_max,
            "status": inv.status.value,
            "status_ru": STATUS_RU[inv.status],
            "candidate_contacts": cand.contacts if revealed else None,
        })
    return out


@router.post("/applications", status_code=201, summary="Откликнуться на вакансию")
async def apply(vacancy_id: str, cover_letter: str = "",
                profile=Depends(get_candidate_profile), db=Depends(get_db)):
    vacancy = await db.get(Vacancy, vacancy_id)
    if vacancy is None or not vacancy.is_active:
        raise HTTPException(404, "Вакансия не найдена")
    dup = (await db.execute(
        select(func.count()).select_from(Application)
        .where(Application.candidate_id == profile.user_id, Application.vacancy_id == vacancy_id)
    )).scalar()
    if dup:
        raise HTTPException(409, "Вы уже откликнулись на эту вакансию")
    app = Application(
        candidate_id=profile.user_id, vacancy_id=vacancy_id,
        cover_letter=cover_letter,
    )
    db.add(app)
    await db.flush()
    return {"id": str(app.id), "status": app.status.value}

@router.get("/candidate/applications", summary="Мои отклики и их статусы")
async def my_applications(profile=Depends(get_candidate_profile), db=Depends(get_db)):
    rows = (await db.execute(
        select(Application).where(Application.candidate_id == profile.user_id)
        .order_by(Application.created_at.desc())
    )).scalars().all()
    out = []
    for a in rows:
        v = await db.get(Vacancy, a.vacancy_id)
        if v is None:
            continue
        out.append({
            "id": str(a.id), "vacancy_id": str(a.vacancy_id), "vacancy_title": v.title,
            "salary_min": v.salary_min, "salary_max": v.salary_max,
            "status": a.status.value, "status_ru": STATUS_RU[a.status],
        })
    return out

@router.post("/employer/applications/{application_id}/decide",
             summary="Обработать отклик кандидата")
async def decide_application(application_id: str, accept: bool,
                             employer=Depends(get_employer_profile), db=Depends(get_db)):
    app = await db.get(Application, application_id)
    if app is None:
        raise HTTPException(404, "Отклик не найден")
    vacancy = await db.get(Vacancy, app.vacancy_id)
    if vacancy is None or vacancy.employer_id != employer.user_id:
        raise HTTPException(403, "Это отклик не на вашу вакансию")
    app.status = InteractionStatus.accepted if accept else InteractionStatus.declined
    if accept:
        app.contact_revealed_at = datetime.now(timezone.utc)
    return {"id": str(app.id), "status": app.status.value}

@router.post("/microtasks", status_code=201,
             summary="Отправить кандидату короткую задачу (регулярные задания)")
async def create_microtask(candidate_id: str, title: str, body_text: str,
                           employer=Depends(get_employer_profile), db=Depends(get_db)):
    accepted = (await db.execute(
        select(func.count()).select_from(Invitation).where(
            Invitation.employer_id == employer.user_id,
            Invitation.candidate_id == candidate_id,
            Invitation.status == InteractionStatus.accepted,
        )
    )).scalar()
    if not accepted:
        raise HTTPException(403, "Кандидат ещё не принял ваше приглашение")
    mt = Microtask(
        candidate_id=candidate_id, employer_id=employer.user_id,
        title=title, body=body_text,
    )
    db.add(mt)
    await db.flush()
    return {"id": str(mt.id), "status": mt.status.value}

@router.get("/employer/vacancy/{vacancy_id}/shortlist",
            summary="Подборка кандидатов под конкретную вакансию")
async def vacancy_shortlist(vacancy_id: str, employer=Depends(get_employer_profile),
                            db=Depends(get_db)):
    v = await _own_vacancy(db, employer, vacancy_id)
    need = EmployerNeed(
        employer_id=employer.user_id,
        raw_text=v.description,
        specialization_code=v.specialization_code,
        min_grade=v.min_grade,
        stack=v.stack,
    )
    started = time.perf_counter()
    items = await build_shortlist(db, need, limit=15, blind=employer.blind_mode)
    return {"vacancy_id": vacancy_id, "title": v.title,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "items": items}


@router.get("/employer/applications", summary="Входящие отклики кандидатов на мои вакансии")
async def employer_applications(employer=Depends(get_employer_profile), db=Depends(get_db)):
    my_vacancies = (await db.execute(
        select(Vacancy).where(Vacancy.employer_id == employer.user_id)
    )).scalars().all()
    vac_map = {v.id: v for v in my_vacancies}
    rows = (await db.execute(
        select(Application).where(Application.vacancy_id.in_(vac_map.keys()))
        .order_by(Application.created_at.desc())
    )).scalars().all()
    out = []
    for a in rows:
        prof = await db.get(CandidateProfile, a.candidate_id)
        out.append({
            "id": str(a.id),
            "vacancy_title": vac_map[a.vacancy_id].title,
            "candidate_id": str(a.candidate_id),
            "candidate_name": prof.full_name,
            "cover_letter": a.cover_letter,
            "status": a.status.value,
            "status_ru": STATUS_RU[a.status],
            "candidate_contacts": prof.contacts if a.contact_revealed_at is not None else None,
        })
    return out


@router.get("/employer/funnel", summary="Воронка найма: вакансии → отклики → приглашения → принятые")
async def employer_funnel(employer=Depends(get_employer_profile), db=Depends(get_db)):
    vac = (await db.execute(
        select(Vacancy).where(Vacancy.employer_id == employer.user_id)
    )).scalars().all()
    vac_ids = [v.id for v in vac]
    apps = 0
    if vac_ids:
        apps = (await db.execute(
            select(func.count()).select_from(Application).where(Application.vacancy_id.in_(vac_ids))
        )).scalar()
    invs = (await db.execute(
        select(Invitation).where(Invitation.employer_id == employer.user_id)
    )).scalars().all()
    sent = len(invs)
    accepted = sum(1 for i in invs if i.status == InteractionStatus.accepted)
    decided = [i for i in invs if i.decided_at is not None]
    avg_hours = round(
        sum((i.decided_at - i.created_at).total_seconds() for i in decided) / len(decided) / 3600,
        1) if decided else None
    return {
        "vacancies": len(vac),
        "applications": apps,
        "invited": sent,
        "accepted": accepted,
        "accept_rate": round(accepted / sent, 3) if sent else None,
        "avg_decision_hours": avg_hours,
    }


@router.get("/employer/candidate/{candidate_id}",
            summary="Страница кандидата для работодателя: категории, история тестов")
async def employer_candidate_view(candidate_id: str, employer=Depends(get_employer_profile),
                                  db=Depends(get_db)):
    c = await db.get(CandidateProfile, candidate_id)
    if c is None:
        raise HTTPException(404, "Кандидат не найден")

    spec_names = {s.code: s.name for s in (await db.execute(select(Specialization))).scalars().all()}
    cats = (await db.execute(
        select(CandidateCategory).where(CandidateCategory.candidate_id == candidate_id)
    )).scalars().all()
    sessions = (await db.execute(
        select(TestSession).where(
            TestSession.candidate_id == candidate_id,
            TestSession.status == TestStatus.completed,
        ).order_by(TestSession.finished_at)
    )).scalars().all()

    revealed = (
        await db.execute(
            select(func.count()).select_from(Invitation).where(
                Invitation.employer_id == employer.user_id,
                Invitation.candidate_id == candidate_id,
                Invitation.contact_revealed_at.is_not(None),
            )
        )
    ).scalar() > 0

    return {
        "candidate_id": candidate_id,
        "full_name": (
            "Кандидат №" + candidate_id[:4].upper()
            if employer.blind_mode and not revealed else c.full_name
        ),
        "stack": c.stack,
        "experience_years": c.experience_years,
        "has_fsp": bool(c.fsp_history),
        "fsp_history": c.fsp_history,
        "fsp_id": c.fsp_id,
        "integrity": round(c.integrity, 2) if c.integrity is not None else 1.0,
        "categories": [
            {"specialization": x.specialization_code, "grade": x.grade.value,
             "category": category_ru(spec_names.get(x.specialization_code, x.specialization_code), x.grade.value),
             "score": final_score(x.theta, c.integrity)}
            for x in cats
        ],
        "history": [
            {**g, "specialization": spec_names.get(g["specialization"], g["specialization"])}
            for g in engine.sessions_history(sessions)
        ],
        "contacts": c.contacts if revealed else None,
    }


@router.get("/candidate/pulse", summary="Пульс профиля: свежесть и дни до остывания")
async def candidate_pulse(candidate=Depends(get_candidate_profile), db=Depends(get_db)):
    from app.services.scoring import freshness_days_left
    if candidate.last_activity_at is None:
        fresh = 0.5
    else:
        days = max(0.0, (datetime.now(timezone.utc) - candidate.last_activity_at).total_seconds() / 86400)
        fresh = min(1.0, math.exp(-days / 21.0))
    return {
        "freshness": round(fresh, 2),
        "days_left": freshness_days_left(candidate.last_activity_at),
        "note": (
            "Профиль свежий — работодатель видит его в топе"
            if fresh >= 0.6 else
            "Профиль остывает: решите микрозадачу или обновите профиль, чтобы подняться в подборках"
        ),
    }


@router.get("/candidate/growth", summary="Путь роста: что поднимет рейтинг и на сколько")
async def candidate_growth(candidate=Depends(get_candidate_profile), db=Depends(get_db)):
    from app.services.scoring import compute_score, GRADE_ORDER, GRADE_RU

    cats = (await db.execute(
        select(CandidateCategory).where(CandidateCategory.candidate_id == candidate.user_id)
    )).scalars().all()
    if not cats:
        return {"steps": [{"action": "Пройдите тестирование — без категории вы невидимы для работодателей", "delta": 0.60}]}

    cat = max(cats, key=lambda x: x.theta)
    base, breakdown = compute_score(candidate, theta_override=cat.theta)

    steps = []
    fresh_now = breakdown["freshness"]["value"]
    if fresh_now < 0.99:
        steps.append({
            "action": "Решите микрозадачу — профиль снова «тёплый»",
            "delta": round(0.10 * (1.0 - fresh_now), 3),
        })
    bounds = {"junior": -0.5, "middle": 0.5, "senior": 1.5, "lead": None}
    target_b = bounds.get(cat.grade.value)
    if target_b is not None:
        theta_target = target_b + 0.25
        delta = 0.60 * (1.0 / (1.0 + math.exp(-theta_target)) - breakdown["theta"]["value"])
        if delta > 0.005:
            next_grade = GRADE_ORDER[GRADE_ORDER.index(cat.grade.value) + 1]
            steps.append({
                "action": f"Пройдите тест на уровень выше ({GRADE_RU[next_grade]})",
                "delta": round(delta, 3),
            })
    fsp_now = breakdown["fsp"]["value"]
    if fsp_now < 0.5:
        steps.append({
            "action": "Укажите ID участника ФСП — подтверждённые турниры дадут вес",
            "delta": round(0.20 * (0.35 - fsp_now), 3),
        })
    steps.sort(key=lambda s: s["delta"], reverse=True)
    return {
        "current_score": round(base, 3),
        "steps": steps[:4],
        "hint": "Каждое действие — конкретный вклад в рейтинг, который видит работодатель",
    }


async def candidate_metrics_data(db, candidate) -> list[dict]:
    from app.services.scoring import compute_score
    cats = (await db.execute(
        select(CandidateCategory).where(CandidateCategory.candidate_id == candidate.user_id)
    )).scalars().all()
    out = []
    for cat in cats:
        rows = (await db.execute(
            select(CandidateCategory.theta, CandidateProfile.integrity)
            .join(CandidateProfile, CandidateProfile.user_id == CandidateCategory.candidate_id)
            .where(CandidateCategory.specialization_code == cat.specialization_code)
        )).all()
        my_score = final_score(cat.theta, candidate.integrity)
        keys = [(final_score(th, integ), th) for th, integ in rows]
        mine = (my_score, cat.theta)
        above = sum(1 for k in keys if k > mine)
        below = sum(1 for k in keys if k < mine)
        total = len(keys)
        _, breakdown = compute_score(candidate, theta_override=cat.theta)
        out.append({
            "specialization": cat.specialization_code,
            "grade": cat.grade.value,
            "category": f"{cat.specialization_code} · {cat.grade.value}",
            "score": my_score,
            "rank": (above + 1) if total else 1,
            "total": total,
            "candidates_in_category": total,
            "percentile": round(100.0 * below / total, 1) if total else 0.0,
            "integrity": round(candidate.integrity, 2) if candidate.integrity is not None else 1.0,
            "breakdown": breakdown,
        })
    return out


@router.get("/candidate/metrics", summary="Мой рейтинг изнутри: балл, место, разложение Score")
async def candidate_metrics(candidate=Depends(get_candidate_profile), db=Depends(get_db)):
    return await candidate_metrics_data(db, candidate)


@router.get("/candidate/microtasks", summary="Мои микрозадачи")
async def my_microtasks(profile=Depends(get_candidate_profile), db=Depends(get_db)):
    rows = (await db.execute(
        select(Microtask).where(Microtask.candidate_id == profile.user_id)
        .order_by(Microtask.created_at.desc())
    )).scalars().all()
    return [
        {"id": str(m.id), "title": m.title, "body": m.body, "status": m.status.value}
        for m in rows
    ]

@router.post("/candidate/microtasks/{microtask_id}/submit",
             summary="Решить задачу или предложить подход")
async def submit_microtask(microtask_id: str, solution: str, approach_only: bool = False,
                           profile=Depends(get_candidate_profile), db=Depends(get_db)):
    mt = await _own_microtask(db, profile, microtask_id)
    if mt.status != MicrotaskStatus.pending:
        raise HTTPException(409, "Задача уже сдана")
    mt.solution = solution
    mt.status = MicrotaskStatus.approach if approach_only else MicrotaskStatus.solved
    mt.answered_at = datetime.now(timezone.utc)

    profile.last_activity_at = datetime.now(timezone.utc)
    return {"id": str(mt.id), "status": mt.status.value}


@router.post("/evaluate", summary="Бенчмарк подбора жюри: пары need→relevant → Precision@k, MRR, nDCG")
async def evaluate(body: dict, k: int = 10, db=Depends(get_db)):
    """Формат ТЗ: «проверяется на тестовом наборе пар „вакансия — кандидат“».

    body: {"pairs": [{"need": "текст потребности", "relevant": ["id", ...]}, ...]}
    Возвращает Precision@k, MRR, nDCG и место релевантных в выдаче.
    """
    results = []
    for pair in body.get("pairs", []):
        try:
            min_grade = Grade(pair["min_grade"]) if pair.get("min_grade") else None
        except ValueError:
            raise HTTPException(422, f"Неизвестный грейд: {pair['min_grade']}")
        need = EmployerNeed(
            employer_id="benchmark",
            raw_text=pair.get("need", ""),
            specialization_code=pair.get("specialization_code"),
            min_grade=min_grade,
            stack=pair.get("stack", []),
        )
        items = await build_shortlist(db, need, limit=max(k * 3, 30))
        ids = [x["candidate_id"] for x in items]
        relevant = set(pair.get("relevant", []))
        top = ids[:k]
        precision = len([i for i in top if i in relevant]) / k if relevant else None
        ranks = [ids.index(i) + 1 for i in relevant if i in ids]
        mrr = float(np.mean([1.0 / r for r in ranks])) if ranks else 0.0
        dcg = sum(1.0 / math.log2(r + 1) for r in ranks)
        ideal = sum(1.0 / math.log2(r + 1) for r in range(1, min(len(relevant), len(ids)) + 1))
        ndcg = dcg / ideal if ideal else 0.0
        results.append({
            "need": pair.get("need", "")[:60],
            "precision_at_k": round(precision, 3) if precision is not None else None,
            "mrr": round(mrr, 3),
            "ndcg": round(ndcg, 3),
            "relevant_in_top": [i for i in top if i in relevant],
            "first_relevant_rank": min(ranks) if ranks else None,
        })
    agg = {
        key: round(float(np.mean([r[key] for r in results if r[key] is not None])), 3)
        for key in ("precision_at_k", "mrr", "ndcg") if any(r.get(key) is not None for r in results)
    }
    return {"k": k, "pairs_evaluated": len(results), "aggregate": agg, "details": results}

