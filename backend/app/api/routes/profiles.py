import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_candidate_profile, get_current_user, get_employer_profile
from app.core.db import get_db
from app.models import CandidateProfile, EmployerProfile
from app.schemas import CandidateProfileIn, CandidateProfileOut, EmployerProfileIn

router = APIRouter(tags=["profiles"])


IMG_EXT = {"jpg", "jpeg", "png", "webp"}

def _safe_image_ext(filename: str | None) -> str:
    ext = (filename or "").rsplit(".", 1)[-1].lower()
    return ext if ext in IMG_EXT else "jpg"

@router.post("/candidate/photo", status_code=201, summary="Загрузить фото профиля")
async def upload_photo(file: UploadFile, profile=Depends(get_candidate_profile)):
    os.makedirs("media/avatars", exist_ok=True)
    path = f"media/avatars/{profile.user_id}.{_safe_image_ext(file.filename)}"
    with open(path, "wb") as f:
        f.write(await file.read())
    profile.photo_url = path
    return {"photo_url": path}


@router.get("/candidate/profile.pdf", summary="Стандартизированный PDF-профиль (автогенерация)")
async def profile_pdf(profile=Depends(get_candidate_profile), db=Depends(get_db)):
    from sqlalchemy import select
    from app.models import CandidateCategory, TestSession, TestStatus
    from app.services.pdf import generate_profile_pdf
    from app.services.testing.engine import sessions_history

    cats = (await db.execute(
        select(CandidateCategory).where(CandidateCategory.candidate_id == profile.user_id)
    )).scalars().all()
    sessions = (await db.execute(
        select(TestSession).where(
            TestSession.candidate_id == profile.user_id,
            TestSession.status == TestStatus.completed,
        ).order_by(TestSession.finished_at)
    )).scalars().all()
    history = sessions_history(sessions)

    from app.api.routes.interaction import candidate_metrics_data
    metrics = await candidate_metrics_data(db, profile)

    verify_url = None
    if profile.grade is not None and profile.specialization_code:
        from app.core.config import settings
        from app.core.security import sign_category
        from app.services.scoring import final_score
        score = final_score(profile.theta, profile.integrity)
        signature = sign_category(str(profile.user_id), profile.specialization_code,
                                  profile.grade.value, score)
        verify_url = f"{settings.frontend_url}/verify/{profile.user_id}/{signature}"

    os.makedirs("media/pdf", exist_ok=True)
    path = f"media/pdf/{profile.user_id}.pdf"
    generate_profile_pdf(profile, metrics, history, path, verify_url)
    return FileResponse(path, filename="profile.pdf")


@router.get("/candidate/certificate.pdf", summary="Сертификат категории с QR-проверкой")
async def certificate_pdf(profile=Depends(get_candidate_profile), db=Depends(get_db)):
    from app.models import Specialization
    from app.services.pdf import generate_certificate_pdf
    from app.services.scoring import final_score
    from app.core.config import settings
    from app.core.security import sign_category

    if profile.grade is None or not profile.specialization_code:
        raise HTTPException(400, "Сначала пройдите тестирование")

    spec = await db.get(Specialization, profile.specialization_code)
    score = final_score(profile.theta, profile.integrity)
    grade = profile.grade.value
    signature = sign_category(str(profile.user_id), profile.specialization_code, grade, score)
    verify_url = f"{settings.frontend_url}/verify/{profile.user_id}/{signature}"

    os.makedirs("media/pdf", exist_ok=True)
    path = f"media/pdf/{profile.user_id}_cert.pdf"
    generate_certificate_pdf(
        profile.full_name or "Кандидат",
        f"{spec.name if spec else profile.specialization_code} · {grade}",
        score, spec.name if spec else "", verify_url, signature, path)
    return FileResponse(path, filename="certificate.pdf")


@router.get("/verify/{user_id}/{signature}", summary="Публичная проверка подлинности категории по QR")
async def verify_certificate(user_id: str, signature: str, db=Depends(get_db)):
    from app.models import Specialization
    from app.services.scoring import final_score
    from app.core.security import verify_category_signature

    profile = await db.get(CandidateProfile, user_id)
    if profile is None or profile.grade is None or not profile.specialization_code:
        return {"valid": False, "reason": "Проверка не найдена"}

    score = final_score(profile.theta, profile.integrity)
    valid = verify_category_signature(
        str(user_id), profile.specialization_code, profile.grade.value, score, signature)
    if not valid:
        return {"valid": False, "reason": "Подпись не совпала — данные менялись после выдачи"}

    spec = await db.get(Specialization, profile.specialization_code)
    return {
        "valid": True,
        "name": profile.full_name,
        "specialization": spec.name if spec else profile.specialization_code,
        "grade": profile.grade.value,
        "score": score,
    }


@router.post("/candidate/resume", summary="Загрузить резюме (PDF) — автораспознавание профиля")
async def parse_resume(file: UploadFile, profile=Depends(get_candidate_profile), db=Depends(get_db)):
    from pypdf import PdfReader
    import io
    from app.services.pdf import parse_resume_pdf
    from app.services.testing.scenarios import SKILLS_CATALOG

    reader = PdfReader(io.BytesIO(await file.read()))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    parsed = parse_resume_pdf(text, SKILLS_CATALOG)
    return {
        "parsed": parsed,
        "note": "Проверьте распознанные данные — они заполнят ваш профиль",
    }


@router.post("/employer/photo", status_code=201, summary="Загрузить логотип компании")
async def upload_employer_photo(file: UploadFile, profile=Depends(get_employer_profile)):
    os.makedirs("media/avatars", exist_ok=True)
    path = f"media/avatars/{profile.user_id}.{_safe_image_ext(file.filename)}"
    with open(path, "wb") as f:
        f.write(await file.read())
    profile.photo_url = path
    return {"photo_url": path}


@router.get("/media/{path:path}", include_in_schema=False)
async def media(path: str, request: Request):
    root = os.path.realpath("media")
    full = os.path.realpath(os.path.join(root, path))
    if os.path.commonpath([full, root]) != root or not os.path.isfile(full):
        raise HTTPException(404, "Файл не найден")
    folder, _, name = path.partition("/")
    if folder == "pdf":
        user = get_current_user(request)
        if name != f"{user.id}.pdf":
            raise HTTPException(403, "Доступ к чужому PDF закрыт")
    elif folder != "avatars":
        raise HTTPException(404, "Файл не найден")
    return FileResponse(full)

@router.put("/candidate/profile", response_model=dict)
async def update_candidate_profile(
    body: CandidateProfileIn, profile=Depends(get_candidate_profile), db=Depends(get_db),
):
    profile.full_name = body.full_name
    profile.contacts = body.contacts
    profile.summary = body.summary
    profile.stack = body.stack
    profile.experience_years = body.experience_years
    profile.soft_skills = body.soft_skills
    profile.last_activity_at = datetime.now(timezone.utc)
    return {"ok": True}

@router.get("/candidate/profile", response_model=CandidateProfileOut)
async def get_candidate_profile_view(profile=Depends(get_candidate_profile)):
    return CandidateProfileOut(
        user_id=str(profile.user_id),
        full_name=profile.full_name,
        contacts=profile.contacts or {},
        summary=profile.summary or "",
        specialization_code=profile.specialization_code,
        grade=profile.grade.value if profile.grade else None,
        theta=profile.theta,
        category=f"{profile.specialization_code} · {profile.grade.value}"
        if profile.grade and profile.specialization_code else None,
        stack=profile.stack,
        experience_years=profile.experience_years,
        fsp_id=profile.fsp_id,
        has_fsp=bool(profile.fsp_history),
        photo_url=profile.photo_url,
        is_public=profile.is_public,
        consent_data_processing=profile.consent_data_processing,
    )

@router.put("/candidate/privacy", summary="Настройки приватности и согласия (152-ФЗ)")
async def update_privacy(
    is_public: bool = True, consent: bool = False,
    profile=Depends(get_candidate_profile),
):
    profile.is_public = is_public
    profile.consent_data_processing = consent
    return {"ok": True, "is_public": is_public, "consent": consent}

@router.put("/employer/profile", response_model=dict)
async def update_employer_profile(
    body: EmployerProfileIn, profile=Depends(get_employer_profile),
):
    profile.company_name = body.company_name
    profile.description = body.description
    profile.industry = body.industry
    profile.contact_email = body.contact_email
    profile.contact_phone = body.contact_phone
    return {"ok": True}

@router.get("/employer/profile", summary="Профиль компании (с фото)")
async def get_employer_profile_view(profile=Depends(get_employer_profile)):
    return {
        "company_name": profile.company_name,
        "description": profile.description,
        "industry": profile.industry,
        "contact_email": profile.contact_email,
        "contact_phone": profile.contact_phone,
        "photo_url": profile.photo_url,
        "blind_mode": profile.blind_mode,
    }

@router.put("/employer/blind", summary="Слепой найм: скрыть ФИО кандидатов до приглашения")
async def toggle_blind(enabled: bool, profile=Depends(get_employer_profile)):
    profile.blind_mode = enabled
    return {"blind_mode": enabled}
