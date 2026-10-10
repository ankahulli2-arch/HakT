import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_confirm_code,
    hash_password,
    verify_password,
)
from app.models import CandidateProfile, EmployerProfile, User, UserRole
from app.schemas import ConfirmIn, LoginIn, RegisterIn, TokenPair

router = APIRouter(tags=["auth"])



@router.post("/auth/register", response_model=dict, status_code=201)
async def register(body: RegisterIn, db: AsyncSession = Depends(get_db)):
    exists = await db.execute(select(User).where(User.email == body.email))
    if exists.scalar_one_or_none():
        raise HTTPException(409, "Email уже зарегистрирован")

    code = generate_confirm_code()
    user = User(
        email=body.email.lower(),
        password_hash=await asyncio.to_thread(hash_password, body.password),
        role=UserRole(body.role),
        confirm_code=code,
    )
    db.add(user)
    await db.flush()
    if user.role == UserRole.candidate:
        db.add(CandidateProfile(user_id=user.id, last_activity_at=datetime.now(timezone.utc)))
    else:
        db.add(EmployerProfile(user_id=user.id))
    print(f"[auth] код подтверждения для {body.email}: {code}")
    return {"user_id": str(user.id), "confirm_code_mvp": code, "message": "Подтвердите email кодом"}

def _pair(sub: str, role: str) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(sub, role),
        refresh_token=create_refresh_token(sub, role),
        role=role,
    )

@router.post("/auth/confirm", response_model=TokenPair)
async def confirm(body: ConfirmIn, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.email == body.email.lower()))).scalar_one_or_none()
    if not user or user.confirm_code != body.code:
        raise HTTPException(400, "Неверный код или email")
    if user.email_confirmed:
        raise HTTPException(409, "Email уже подтверждён")
    user.email_confirmed = True
    user.confirm_code = None
    return _pair(str(user.id), user.role.value)

@router.post("/auth/login", response_model=TokenPair)
async def login(body: LoginIn, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.email == body.email.lower()))).scalar_one_or_none()
    if not user or not await asyncio.to_thread(verify_password, body.password, user.password_hash):
        raise HTTPException(401, "Неверный email или пароль")
    if not user.email_confirmed:
        raise HTTPException(403, "Подтвердите email")
    return _pair(str(user.id), user.role.value)

@router.post("/auth/refresh", response_model=TokenPair)
async def refresh(refresh_token: str):
    try:
        payload = decode_token(refresh_token)
    except Exception:
        raise HTTPException(401, "Недействительный refresh-токен")
    if payload.get("typ") != "refresh":
        raise HTTPException(401, "Ожидался refresh-токен")
    role = payload.get("role", "candidate")
    return _pair(payload["sub"], role)
