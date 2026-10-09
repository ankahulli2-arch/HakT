import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import decode_token
from app.models import CandidateProfile, EmployerProfile, User, UserRole

def get_current_user(request: Request) -> User:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Требуется авторизация")
    try:
        payload = decode_token(auth.removeprefix("Bearer "))
    except jwt.PyJWTError:
        raise HTTPException(401, "Недействительный токен")
    if payload.get("typ") != "access":
        raise HTTPException(401, "Недействительный токен")
    request.state.user_id = payload["sub"]
    request.state.role = payload["role"]
    return User(id=payload["sub"], role=UserRole(payload["role"]), email="")

def require_role(role: UserRole):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role != role:
            raise HTTPException(403, f"Доступно только для роли {role.value}")
        return user
    return checker

async def get_candidate_profile(
    user: User = Depends(require_role(UserRole.candidate)),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfile:
    profile = await db.get(CandidateProfile, user.id)
    if profile is None:
        raise HTTPException(404, "Профиль кандидата не найден")
    return profile

async def get_employer_profile(
    user: User = Depends(require_role(UserRole.employer)),
    db: AsyncSession = Depends(get_db),
) -> EmployerProfile:
    profile = await db.get(EmployerProfile, user.id)
    if profile is None:
        raise HTTPException(404, "Профиль работодателя не найден")
    return profile
