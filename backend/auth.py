import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import ApiKey, User, get_session


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_minutes)
    to_encode = {"sub": user_id, "exp": expire, "type": "access"}
    return jwt.encode(
        to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_days)
    to_encode = {"sub": user_id, "exp": expire, "type": "refresh"}
    return jwt.encode(
        to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token") from e


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def generate_api_key() -> tuple[str, str, str]:
    plain = f"mk_{secrets.token_urlsafe(24)}"
    hashed = hashlib.sha256(plain.encode()).hexdigest()
    prefix = plain[:8]
    return plain, hashed, prefix


async def validate_api_key(key: str, session: AsyncSession) -> Optional[User]:
    if not key.startswith("mk_"):
        return None

    key_hash = hashlib.sha256(key.encode()).hexdigest()
    result = await session.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
    api_key = result.scalar_one_or_none()

    if not api_key:
        return None

    await session.execute(
        update(ApiKey)
        .where(ApiKey.id == api_key.id)
        .values(last_used_at=datetime.now(timezone.utc))
    )

    result = await session.execute(select(User).where(User.id == api_key.user_id))
    return result.scalar_one_or_none()


def _get_fernet():
    import base64
    from cryptography.fernet import Fernet

    key = settings.encryption_key
    if len(key) != 44:
        key_bytes = key.encode()[:32].ljust(32, b"0")
        key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(key)


def encrypt_token(token: str) -> str:
    return _get_fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    return _get_fernet().decrypt(encrypted.encode()).decode()


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_username(session: AsyncSession, username: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    email: str,
    username: str,
    password: str,
) -> User:
    user = User(
        email=email,
        username=username,
        password_hash=hash_password(password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate_user(
    session: AsyncSession,
    username_or_email: str,
    password: str,
) -> Optional[User]:
    result = await session.execute(
        select(User).where(
            (User.email == username_or_email) | (User.username == username_or_email)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        return None

    return user


def get_google_auth_url(state: str) -> str:
    return (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.google_client_id}"
        f"&redirect_uri={settings.google_redirect_uri}"
        f"&response_type=code"
        f"&scope=openid%20email%20profile%20https://www.googleapis.com/auth/gmail.readonly"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state={state}"
    )


async def exchange_google_code(code: str) -> dict:
    from authlib.integrations.httpx_client import AsyncOAuth2Client

    async with AsyncOAuth2Client() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        return response.json()


async def refresh_google_token(refresh_token: str) -> dict:
    from authlib.integrations.httpx_client import AsyncOAuth2Client

    async with AsyncOAuth2Client() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "refresh_token": refresh_token,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        return response.json()
