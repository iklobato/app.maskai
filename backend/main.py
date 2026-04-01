import asyncio
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    create_user,
    encrypt_token,
    exchange_google_code,
    generate_api_key,
    get_current_user,
    get_google_auth_url,
    get_user_by_email,
    get_user_by_username,
)
from backend.config import settings
from backend.database import ApiKey, ConnectedAccount, Subscription, User, get_session
from backend.sync import sync_account_emails, check_account_limit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="maskai", description="MCP server for email intelligence")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="frontend"), name="frontend")


async def require_auth(user: User = Depends(get_current_user)) -> User:
    return user


@app.post("/api/auth/register")
async def register(
    email: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    if await get_user_by_email(session, email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if await get_user_by_username(session, username):
        raise HTTPException(status_code=400, detail="Username already taken")

    user = await create_user(session, email, username, password)
    response = RedirectResponse(url="/#dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=create_access_token(user.id),
        httponly=True,
        secure=settings.env == "production",
        samesite="lax",
        max_age=settings.jwt_access_minutes * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=create_refresh_token(user.id),
        httponly=True,
        secure=settings.env == "production",
        samesite="lax",
        max_age=settings.jwt_refresh_days * 86400,
    )
    return response


@app.post("/api/auth/login")
async def login(
    username_or_email: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    user = await authenticate_user(session, username_or_email, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    response = RedirectResponse(url="/#dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=create_access_token(user.id),
        httponly=True,
        secure=settings.env == "production",
        samesite="lax",
        max_age=settings.jwt_access_minutes * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=create_refresh_token(user.id),
        httponly=True,
        secure=settings.env == "production",
        samesite="lax",
        max_age=settings.jwt_refresh_days * 86400,
    )
    return response


@app.post("/api/auth/logout")
async def logout():
    response = RedirectResponse(url="/#login", status_code=303)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response


@app.get("/api/auth/me")
async def me(user: User = Depends(require_auth)):
    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
    }


@app.get("/api/auth/google/start")
async def google_auth_start(user: User = Depends(require_auth)):
    state_data = user.id
    state = secrets.token_urlsafe(32)
    url = get_google_auth_url(state)
    return {"url": url, "state": state_data}


@app.get("/api/auth/google/callback")
async def google_auth_callback(
    code: str = Query(...),
    state: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    if not state:
        raise HTTPException(status_code=400, detail="Missing state")

    user_id = state
    tokens = await exchange_google_code(code)

    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token", "")

    import httpx

    async with httpx.AsyncClient() as client:
        user_info = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_info.raise_for_status()
        info = user_info.json()

    existing = await session.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.user_id == user_id,
            ConnectedAccount.email_address == info["email"],
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Account already connected")

    current_accounts_result = await session.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.user_id == user_id,
            ConnectedAccount.status == "active",
        )
    )
    current_count = len(current_accounts_result.scalars().all())

    sub_result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    subscription = sub_result.scalar_one_or_none()
    try:
        check_account_limit(
            subscription.tier if subscription else "free", current_count
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

    account = ConnectedAccount(
        user_id=user_id,
        provider="google",
        email_address=info["email"],
        display_name=info.get("name"),
        access_token_encrypted=encrypt_token(access_token),
        refresh_token_encrypted=encrypt_token(refresh_token) if refresh_token else None,
        token_expires_at=datetime.fromtimestamp(
            tokens.get("expires_in", 0), tz=timezone.utc
        )
        if "expires_in" in tokens
        else None,
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)

    asyncio.create_task(sync_account_emails(account.id))

    return RedirectResponse(url="/#dashboard?connected=true", status_code=303)


@app.post("/api/keys")
async def create_api_key(
    name: str = Form(...),
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    plain, hashed, prefix = generate_api_key()
    api_key = ApiKey(
        user_id=user.id,
        key_hash=hashed,
        key_prefix=prefix,
        name=name,
    )
    session.add(api_key)
    await session.commit()
    return {"id": str(api_key.id), "key": plain, "name": name, "prefix": prefix}


@app.get("/api/keys")
async def list_api_keys(
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user.id)
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        {
            "id": str(key.id),
            "name": key.name,
            "prefix": key.key_prefix,
            "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
            "created_at": key.created_at.isoformat(),
        }
        for key in keys
    ]


@app.delete("/api/keys/{key_id}")
async def delete_api_key(
    key_id: str,
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    await session.delete(key)
    await session.commit()
    return {"message": "Key revoked"}


@app.get("/api/subscription")
async def get_subscription(
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    sub_result = await session.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = sub_result.scalar_one_or_none()
    if not subscription:
        return {"tier": "free", "status": "inactive"}
    return {
        "tier": subscription.tier,
        "status": subscription.status,
        "current_period_end": (
            subscription.current_period_end.isoformat()
            if subscription.current_period_end
            else None
        ),
    }


@app.post("/api/subscription/checkout")
async def subscription_checkout(
    tier: str = Form(...),
    user: User = Depends(require_auth),
):
    from backend.payments import StripePaymentProvider

    payment = StripePaymentProvider()
    success_url = f"{settings.app_url}/#dashboard?subscribed=true"
    cancel_url = f"{settings.app_url}/#dashboard?canceled=true"
    checkout_url = payment.create_checkout(user.id, tier, success_url, cancel_url)
    return {"url": checkout_url}


@app.post("/api/subscription/portal")
async def subscription_portal(
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    from backend.payments import StripePaymentProvider

    sub_result = await session.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = sub_result.scalar_one_or_none()
    if not subscription or not subscription.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No subscription found")
    payment = StripePaymentProvider()
    portal_url = payment.create_portal(
        subscription.stripe_customer_id, settings.app_url
    )
    return {"url": portal_url}


@app.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request):
    from backend.payments import StripePaymentProvider

    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    payment = StripePaymentProvider()
    try:
        await payment.handle_webhook(payload, sig)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"received": True}


@app.get("/api/health")
async def health():
    try:
        async for session in get_session():
            await session.execute(select(1))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


from fastapi.responses import FileResponse
import os


@app.get("/")
async def root():
    path = os.path.join("frontend", "index.html")
    return FileResponse(path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
