from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets

import bcrypt
import jwt

from app.core.config import settings

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False

def create_access_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
        "typ": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")

def create_refresh_token(user_id: str, role: str = "candidate") -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        "typ": "refresh",
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])

def generate_confirm_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"

def sign_category(user_id: str, specialization: str, grade: str, score: int) -> str:
    raw = f"cert-v1|{user_id}|{specialization}|{grade}|{score}"
    return hmac.new(settings.secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()

def verify_category_signature(user_id: str, specialization: str, grade: str,
                              score: int, signature: str) -> bool:
    return hmac.compare_digest(
        sign_category(user_id, specialization, grade, score), signature or "")
