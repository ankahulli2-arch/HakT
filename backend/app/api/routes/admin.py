import asyncio
import os
import random
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import hash_password
from app.api.routes.fsp import MOCK_REGISTRY
from app.models import (
    CandidateCategory,
    CandidateProfile,
    EmployerProfile,
    FspAchievement,
    ItemTemplate,
    Specialization,
    User,
    UserRole,
    Vacancy,
)
from app.services.scoring import fsp_index, theta_to_grade, board_key
from app.services.testing.blueprint import make_draft, publish
from app.services.testing.scenarios import SCENARIOS, build_bank_items

router = APIRouter(prefix="/admin", tags=["admin"])

MALE = (["Алексей", "Дмитрий", "Сергей", "Иван", "Павел", "Кирилл", "Андрей",
         "Николай", "Виктор", "Максим"],
        ["Смирнов", "Орлов", "Попов", "Соколов", "Морозов", "Зайцев", "Семёнов",
         "Виноградов", "Ковалёв", "Кузнецов", "Васильев", "Павлов", "Голубев", "Богданов"])
FEMALE = (["Мария", "Анна", "Елена", "Ольга", "Наталья", "Юлия", "Татьяна",
           "Светлана", "Ирина", "Полина"],
          ["Ковалёва", "Кузнецова", "Васильева", "Новикова", "Волкова", "Павлова",
           "Голубева", "Богданова"])

EXTRA_VACANCIES = [
    {"emp": 1, "spec": "backend", "title": "Java-разработчик (Spring)",
     "stack": ["java", "spring", "postgresql", "kafka"], "min_grade": "senior",
     "salary_min": 280000, "salary_max": 450000, "code_language": "java",
     "description": "Микросервисы платёжного ядра: Java, Spring Boot, событийная интеграция."},
    {"emp": 1, "spec": "frontend", "title": "React Native-разработчик",
     "stack": ["react native", "javascript", "typescript"], "min_grade": "middle",
     "salary_min": 170000, "salary_max": 290000, "code_language": "javascript",
     "description": "Мобильное приложение банка: React Native, биометрия, push-уведомления."},
    {"emp": 1, "spec": "ml", "title": "ML-инженер (поиск и рекомендации)",
     "stack": ["python", "pytorch", "lightgbm", "nltk"], "min_grade": "middle",
     "salary_min": 230000, "salary_max": 380000, "code_language": "python",
     "description": "Рекомендации продуктов в платёжном приложении: ранжирующие модели, A/B."},
    {"emp": 2, "spec": "analytics", "title": "Data Engineer",
     "stack": ["airflow", "spark", "airbyte", "etl"], "min_grade": "senior",
     "salary_min": 220000, "salary_max": 360000, "code_language": "python",
     "description": "Пайплайны данных: Airflow, Spark, витрины для ML-моделей."},
    {"emp": 2, "spec": "backend", "title": "C++-разработчик (высокие нагрузки)",
     "stack": ["c++", "linux", "redis"], "min_grade": "senior",
     "salary_min": 300000, "salary_max": 520000, "code_language": "c++",
     "description": "Движок сопоставления заявок: современный C++, задержка отклика менее миллисекунды."},
    {"emp": 2, "spec": "qa", "title": "QA-автоматизатор (Playwright)",
     "stack": ["playwright", "javascript", "ci/cd"], "min_grade": "middle",
     "salary_min": 140000, "salary_max": 230000, "code_language": "javascript",
     "description": "E2E-тесты аналитической платформы: Playwright, отчёты, контур CI."},
    {"emp": 3, "spec": "devops", "title": "Системный администратор Linux",
     "stack": ["linux", "bash", "ansible", "nginx"], "min_grade": "junior",
     "salary_min": 90000, "salary_max": 150000, "code_language": "python",
     "description": "On-premise-инфраструктура СЭД: серверы, бэкапы, мониторинг."},
    {"emp": 3, "spec": "analytics", "title": "Аналитик-программист 1С",
     "stack": ["1с", "sql", "excel"], "min_grade": "middle",
     "salary_min": 120000, "salary_max": 200000, "code_language": "python",
     "description": "Учёт и отчётность на платформе 1С, обмены данными с СЭД."},
    {"emp": 4, "spec": "frontend", "title": "Android-разработчик (Kotlin)",
     "stack": ["kotlin", "java"], "min_grade": "middle",
     "salary_min": 160000, "salary_max": 280000, "code_language": "java",
     "description": "Приложение лояльности сети: Kotlin, экраны скидок, офлайн-режим."},
    {"emp": 4, "spec": "backend", "title": "C#-разработчик (.NET)",
     "stack": ["c#", "asp.net", "postgresql"], "min_grade": "middle",
     "salary_min": 160000, "salary_max": 280000, "code_language": "c#",
     "description": "Корпоративные сервисы ритейл-сети: ASP.NET, интеграции с кассами."},
    {"emp": 1, "spec": "backend", "title": "Go-разработчик (платёжный шлюз)",
     "stack": ["go", "redis", "postgresql"], "min_grade": "middle",
     "salary_min": 190000, "salary_max": 310000, "code_language": "python",
     "description": "Очереди платежей на Go: высокая нагрузка, ретраи, идемпотентность."},
    {"emp": 1, "spec": "devops", "title": "Инженер защиты приложений (AppSec)",
     "stack": ["security", "linux", "docker"], "min_grade": "middle",
     "salary_min": 190000, "salary_max": 320000, "code_language": "python",
     "description": "Безопасность приложений: ревью кода, модель угроз, конвейеры CI/CD."},
    {"emp": 2, "spec": "ml", "title": "MLOps-инженер",
     "stack": ["python", "mlflow", "docker"], "min_grade": "middle",
     "salary_min": 200000, "salary_max": 330000, "code_language": "python",
     "description": "Жизненный цикл моделей: mlflow, реестр, сервинг, мониторинг."},
    {"emp": 2, "spec": "frontend", "title": "Frontend-разработчик (визуализации)",
     "stack": ["typescript", "react"], "min_grade": "middle",
     "salary_min": 150000, "salary_max": 260000, "code_language": "javascript",
     "description": "Интерактивные графики и дашборды: drill-down, экспорт, тёмная тема."},
    {"emp": 2, "spec": "analytics", "title": "Scala-разработчик (Spark)",
     "stack": ["scala", "spark", "clickhouse"], "min_grade": "senior",
     "salary_min": 250000, "salary_max": 400000, "code_language": "java",
     "description": "Потоковая аналитика: spark-джобы, clickhouse, витрины для BI."},
    {"emp": 3, "spec": "frontend", "title": "Vue-разработчик (личный кабинет)",
     "stack": ["vue", "javascript"], "min_grade": "junior",
     "salary_min": 100000, "salary_max": 170000, "code_language": "javascript",
     "description": "Личный кабинет клиента на Vue: заявки, документы, оплата."},
    {"emp": 3, "spec": "devops", "title": "DevOps-инженер (Kubernetes)",
     "stack": ["kubernetes", "helm", "gitlab ci"], "min_grade": "middle",
     "salary_min": 170000, "salary_max": 280000, "code_language": "python",
     "description": "Платформа выдачи услуг: k8s, helm-чарты, пайплайны в GitLab."},
    {"emp": 4, "spec": "qa", "title": "QA-инженер (мобильные приложения)",
     "stack": ["android", "ios", "postman"], "min_grade": "middle",
     "salary_min": 130000, "salary_max": 210000, "code_language": "python",
     "description": "Тестирование приложения лояльности: чек-листы, регресс, баг-репорты."},
    {"emp": 4, "spec": "backend", "title": "Go-разработчик (складская логистика)",
     "stack": ["go", "postgresql", "rabbitmq"], "min_grade": "middle",
     "salary_min": 180000, "salary_max": 300000, "code_language": "python",
     "description": "Сервисы склада: заказы, остатки, интеграции с кассами."},
    {"emp": 4, "spec": "analytics", "title": "Аналитик данных (Power BI)",
     "stack": ["power bi", "sql", "excel"], "min_grade": "junior",
     "salary_min": 100000, "salary_max": 160000, "code_language": "python",
     "description": "Отчёты ритейла в Power BI: продажи, остатки, оборачиваемость."},
]


ELLE_SUMMARY = ("ML-инженер с практическим опытом разработки и обучения нейросетей для задач "
                "компьютерного зрения и медицинской визуализации. Работаю с PyTorch, обучаю и "
                "оптимизирую модели сегментации, классификации и детекции, включая многозадачные "
                "архитектуры. Умею быстро разбираться в новых доменах, самостоятельно ставить "
                "задачи и доводить проекты до результата.")


@router.post("/seed", summary="Наполнить базу демо-данными (reset=true — полный сброс для жюри)")
async def seed(reset: bool = False, db: AsyncSession = Depends(get_db)):
    if reset:
        from sqlalchemy import text
        from app.core.db import Base, engine
        from app.core.redisio import client as redis_client
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        try:
            await redis_client.flushdb()
        except Exception:
            pass

    count = (await db.execute(select(func.count(Specialization.code)))).scalar()
    if count:
        return {"seeded": False, "reason": "данные уже есть"}

    rng = random.Random(2026)

    for sc in SCENARIOS:
        db.add(Specialization(code=sc.spec_code, name=sc.spec_name,
                              description=sc.spec_description,
                              survey_options=sc.survey_options))
        for item in build_bank_items(sc):
            db.add(ItemTemplate(**item))

    employers_data = [
        ("techlog@techlogistics.ru", "АйтиЛайт", "Разработка веб-сервисов, платформ и ML-продуктов", "IT-разработка"),
        ("hr@finpay.ru", "ФинПэй", "Платёжный шлюз и финансовые сервисы", "Финтех"),
        ("jobs@dataminds.ru", "ДатаМайндс", "Продуктовая аналитика и ML", "Аналитика"),
        ("office@artel.ru", "Артель", "Корпоративные услуги и документооборот", "Услуги"),
        ("people@retailpro.ru", "РитейлПро", "Сеть розничных магазинов", "Ритейл"),
    ]
    employer_ids = []
    emp_hash = await asyncio.to_thread(hash_password, "Employer2026!")
    for email, company, desc, industry in employers_data:
        u = User(id=uuid.uuid5(uuid.NAMESPACE_DNS, email), email=email,
                 password_hash=emp_hash, role=UserRole.employer, email_confirmed=True)
        db.add(u)
        await db.flush()
        it = company == "АйтиЛайт"
        db.add(EmployerProfile(user_id=u.id, company_name=company, description=desc,
                               industry=industry,
                               contact_email=("hello@aitilight.ru" if it else email),
                               contact_phone=("+7 495 320-45-67" if it else ""),
                               photo_url=(f"media/avatars/{u.id}.jpg" if it else None)))
        employer_ids.append(u.id)

    vi = 0
    for spec_code, vacancies in ((sc.spec_code, sc.demo_vacancies) for sc in SCENARIOS):
        for v in vacancies:
            db.add(Vacancy(employer_id=employer_ids[vi % len(employer_ids)], title=v["title"],
                           description=v["description"], specialization_code=spec_code,
                           min_grade=v["min_grade"], stack=v["stack"],
                           code_language=v.get("code_language", "python"),
                           salary_min=v["salary_min"], salary_max=v["salary_max"]))
            vi += 1
    for v in EXTRA_VACANCIES:
        db.add(Vacancy(employer_id=employer_ids[v["emp"]], title=v["title"],
                       description=v["description"], specialization_code=v["spec"],
                       min_grade=v["min_grade"], stack=v["stack"],
                       code_language=v.get("code_language", "python"),
                       salary_min=v["salary_min"], salary_max=v["salary_max"]))
        vi += 1

    first_vac = (await db.execute(
        select(Vacancy).where(Vacancy.employer_id == employer_ids[0]).limit(1)
    )).scalars().first()
    if first_vac is not None:
        bp = await make_draft(db, employer_ids[0], first_vac.specialization_code,
                              first_vac.title, use_web=False,
                              vacancy_id=str(first_vac.id),
                              code_language=first_vac.code_language or "python")
        await publish(db, bp)

    fsp_ids = list(MOCK_REGISTRY.keys())
    now = datetime.now(timezone.utc)
    cand_hash = await asyncio.to_thread(hash_password, "Candidate2026!")
    cand_ids: list[str] = []
    for i in range(150):
        sc = rng.choice(SCENARIOS)
        spec = sc.spec_code
        true_theta = max(-2.5, min(2.5, rng.gauss(0, 1.1)))
        firsts, lasts = rng.choice([MALE, FEMALE])
        name = f"{rng.choice(firsts)} {rng.choice(lasts)}"
        email = f"demo_cand_{i:03d}@example.ru"

        has_fsp = (rng.random() < 0.35) or i == 50
        fsp_id = fsp_ids[i % len(fsp_ids)] if has_fsp else None
        fsp_history = MOCK_REGISTRY[fsp_id]["achievements"] if has_fsp else None

        u = User(id=uuid.uuid5(uuid.NAMESPACE_DNS, email), email=email,
                 password_hash=cand_hash, role=UserRole.candidate, email_confirmed=True)
        db.add(u)
        await db.flush()
        cand_ids.append(str(u.id))
        prof = CandidateProfile(
            user_id=u.id, full_name=name,
            contacts={"email": email, "telegram": f"@cand_{i:03d}",
                      "phone": f"+7 9{rng.randint(100, 999)} {rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(10, 99)}"},
            summary=f"{theta_to_grade(true_theta)} {spec}",
            stack=rng.sample(sc.stack_tags, k=min(len(sc.stack_tags), rng.randint(2, 5)))
            if sc.stack_tags else [],
            experience_years=rng.choice([0.5, 1, 2, 3, 5, 8]),
            specialization_code=spec, grade=theta_to_grade(true_theta),
            theta=round(true_theta, 2), theta_se=0.3,
            theta_history=[round(true_theta, 2)],
            last_grade_change_at=now - timedelta(days=rng.randint(95, 200)),
            last_activity_at=now - timedelta(days=(rng.randint(0, 5) if i < 3 else rng.randint(0, 60))),
            fsp_id=fsp_id, fsp_history=fsp_history,
            is_public=True, consent_data_processing=True,
        )
        if i == 50:
            prof.full_name = "Элка Роднева"
            prof.contacts = {"email": email, "telegram": "@Elle", "phone": "+7 999 000-00-10"}
            prof.summary = ELLE_SUMMARY
            prof.stack = ["python", "pytorch", "ml", "sql"]
            prof.experience_years = 4.0
            prof.specialization_code = "ml"
            prof.grade = theta_to_grade(1.2)
            prof.theta, prof.theta_se = 1.2, 0.3
            prof.theta_history = [1.2]
            prof.photo_url = f"media/avatars/{u.id}.jpg"
        db.add(prof)
        await db.flush()
        if has_fsp:
            for a in fsp_history:
                db.add(FspAchievement(fsp_id=fsp_id, kind=a["kind"], title=a["title"],
                                      level=a["level"], result=a["result"], year=a["year"],
                                      weight=fsp_index([a])))
        cat = CandidateCategory(candidate_id=u.id, specialization_code=spec,
                                grade=theta_to_grade(true_theta), theta=round(true_theta, 2),
                                theta_se=0.3)
        if i == 50:
            cat.specialization_code = "ml"
            cat.grade = theta_to_grade(1.2)
            cat.theta = 1.2
        db.add(cat)
        await db.flush()

    await db.flush()
    assets = Path(__file__).resolve().parent.parent.parent / "assets"
    os.makedirs("media/avatars", exist_ok=True)
    for uid, fname in (
        (str(uuid.uuid5(uuid.NAMESPACE_DNS, employers_data[0][0])), "it_logo.jpg"),
        (str(uuid.uuid5(uuid.NAMESPACE_DNS, "demo_cand_050@example.ru")), "elle_photo.jpg"),
    ):
        src = assets / fname
        if src.exists():
            shutil.copyfile(src, os.path.join("media", "avatars", f"{uid}.jpg"))
    from app.core.redisio import client as redis_client
    from app.models import Application, Grade, Invitation, InteractionStatus, TestSession, TestStatus
    techlog = employer_ids[0]
    tl_vacs = (await db.execute(
        select(Vacancy).where(Vacancy.employer_id == techlog)
    )).scalars().all()
    demo_ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, f"demo_cand_{i:03d}@example.ru")) for i in range(3)]
    for k, cid in enumerate(demo_ids + [cand_ids[rng.randrange(len(cand_ids))] for _ in range(3)]):
        if tl_vacs:
            db.add(Application(candidate_id=cid, vacancy_id=tl_vacs[k % len(tl_vacs)].id,
                               cover_letter="Заинтересовали задачи, готов обсудить условия"))
    invitees = [demo_ids[0], demo_ids[1]] + [cand_ids[rng.randrange(len(cand_ids))] for _ in range(2)]
    for k, (cid, inv_status) in enumerate(zip(invitees, [
            InteractionStatus.accepted, InteractionStatus.viewed,
            InteractionStatus.sent, InteractionStatus.accepted])):
        decided = (now - timedelta(hours=rng.randint(5, 50))
                   if inv_status in (InteractionStatus.accepted, InteractionStatus.viewed) else None)
        db.add(Invitation(
            employer_id=techlog, candidate_id=cid,
            vacancy_id=tl_vacs[k % len(tl_vacs)].id if tl_vacs else None,
            message="Нам подошёл ваш профиль категории — приглашаем на позицию",
            salary_min=180000, salary_max=300000, status=inv_status,
            contact_revealed_at=decided if inv_status == InteractionStatus.accepted else None,
            decided_at=decided,
            created_at=now - timedelta(hours=rng.randint(55, 140)),
        ))
    await db.flush()
    db.add(TestSession(
        candidate_id=demo_ids[1], specialization_code="backend",
        target_grade=Grade.junior, is_initial=True, status=TestStatus.completed,
        theta=-2.75, se=0.42, administered=[], measured_grade=Grade.junior,
        integrity=0.7, started_at=now - timedelta(hours=30), finished_at=now - timedelta(hours=29),
    ))
    await db.flush()

    cats = (await db.execute(select(CandidateCategory))).scalars().all()
    dev = sorted((c for c in cats if c.specialization_code == "devops"),
                 key=lambda c: -c.theta)
    for row, theta in zip(dev, (2.31, 2.20)):
        row.theta = theta
        prof = await db.get(CandidateProfile, row.candidate_id)
        if prof is not None:
            prof.theta = theta
            prof.theta_history = [theta]
    await db.flush()
    board: dict[str, dict[str, float]] = {}
    profs = {p.user_id: p for p in (await db.execute(select(CandidateProfile))).scalars().all()}
    for c in cats:
        integ = profs[c.candidate_id].integrity if c.candidate_id in profs else None
        board.setdefault(c.specialization_code, {})[str(c.candidate_id)] = board_key(c.theta, integ)
    for spec, mapping in board.items():
        try:
            await redis_client.zadd(f"leaderboard:{spec}", mapping)
        except Exception:
            break
    return {"seeded": True, "candidates": 150, "specializations": len(SCENARIOS), "vacancies": vi}


@router.post("/validate", summary="Живая валидация: синтетика через продуктовый CAT-движок")
async def validate(limit: int = 300):
    from app.services.validation import run_validation
    return await asyncio.to_thread(run_validation, min(1500, max(50, limit)))
