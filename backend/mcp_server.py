import logging
from datetime import datetime, timezone
from typing import Annotated, Optional
from uuid import UUID

from fastmcp import Context, FastMCP
from fastmcp.dependencies import CurrentAccessToken
from fastmcp.server.auth import AccessToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import ConnectedAccount, Email, User, get_session
from backend.sync import incremental_sync, search_similar
from backend.auth import decrypt_token, validate_api_key

logger = logging.getLogger(__name__)

mcp = FastMCP("maskai")


async def get_user_from_token(token: AccessToken) -> Optional[User]:
    async for session in get_session():
        user = await validate_api_key(token.claims.get("key", ""), session)
        if not user:
            user_id = token.claims.get("sub")
            if user_id:
                result = await session.execute(
                    select(User).where(User.id == UUID(user_id))
                )
                user = result.scalar_one_or_none()
        return user


@mcp.tool()
async def list_accounts(
    ctx: Context,
) -> list[dict]:
    """List all email accounts connected to the user's account."""
    token = ctx.request_context.auth_info
    if not token:
        return []

    user = await get_user_from_token(token)
    if not user:
        return []

    result_list: list[dict] = []
    async for session in get_session():
        result = await session.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.user_id == user.id, ConnectedAccount.status == "active"
            )
        )
        accounts = result.scalars().all()

        result_list = [
            {
                "id": str(acc.id),
                "provider": acc.provider,
                "email": acc.email_address,
                "display_name": acc.display_name,
                "status": acc.status,
                "sync_status": acc.sync_status,
                "emails_synced": acc.emails_synced,
            }
            for acc in accounts
        ]
        break
    return result_list


@mcp.tool()
async def search_emails(
    query: str,
    ctx: Context,
    limit: int = 10,
    account_id: Optional[str] = None,
) -> list[dict]:
    """Search emails using natural language. The system understands semantic meaning."""
    token = ctx.request_context.auth_info
    if not token:
        return []

    user = await get_user_from_token(token)
    if not user:
        return []

    result_list: list[dict] = []
    async for session in get_session():
        if account_id:
            account_ids = [UUID(account_id)]
        else:
            result = await session.execute(
                select(ConnectedAccount.id).where(
                    ConnectedAccount.user_id == user.id,
                    ConnectedAccount.status == "active",
                )
            )
            account_ids = [row[0] for row in result.fetchall()]

        if not account_ids:
            break

        for acc_id in account_ids:
            result = await session.execute(
                select(ConnectedAccount).where(ConnectedAccount.id == acc_id)
            )
            account = result.scalar_one_or_none()
            if account:
                await incremental_sync(acc_id)

        emails = await search_similar(session, account_ids, query, limit)

        result_list = [
            {
                "id": str(email.id),
                "account_id": str(email.account_id),
                "subject": email.subject,
                "sender": email.sender,
                "recipients": email.recipients,
                "date": email.date.isoformat() if email.date else None,
                "snippet": email.snippet,
                "labels": email.labels or [],
            }
            for email in emails
        ]
        break
    return result_list


@mcp.tool()
async def get_email(
    email_id: str,
    ctx: Context,
) -> Optional[dict]:
    """Get full details of a specific email including body content."""
    token = ctx.request_context.auth_info
    if not token:
        return None

    user = await get_user_from_token(token)
    if not user:
        return None

    async for session in get_session():
        result = await session.execute(
            select(Email, ConnectedAccount)
            .join(ConnectedAccount)
            .where(
                Email.id == UUID(email_id),
                ConnectedAccount.user_id == user.id,
            )
        )
        row = result.first()
        if not row:
            return None

        email, account = row

        try:
            from backend.auth import decrypt_token
            from backend.email import get_provider as get_email_provider

            access_token = decrypt_token(account.access_token_encrypted)
            email_provider = get_email_provider(account.provider)

            if email_provider is not None:
                body = await email_provider.get_email_body(
                    access_token, email.provider_message_id
                )
            else:
                body = email.snippet or ""

            return {
                "id": str(email.id),
                "account_id": str(email.account_id),
                "subject": email.subject,
                "sender": email.sender,
                "recipients": email.recipients,
                "date": email.date.isoformat() if email.date else None,
                "snippet": email.snippet,
                "labels": email.labels or [],
                "body": body,
                "thread_id": email.thread_id,
            }
        except Exception as e:
            logger.error(f"Failed to fetch email detail: {e}")
            return {
                "id": str(email.id),
                "account_id": str(email.account_id),
                "subject": email.subject,
                "sender": email.sender,
                "date": email.date.isoformat() if email.date else None,
                "snippet": email.snippet,
                "body": "(Failed to fetch full body)",
            }


@mcp.tool()
async def get_recent_emails(
    ctx: Context,
    limit: int = 20,
    account_id: Optional[str] = None,
) -> list[dict]:
    """Get recent emails from inbox."""
    token = ctx.request_context.auth_info
    if not token:
        return []

    user = await get_user_from_token(token)
    if not user:
        return []

    result_list: list[dict] = []
    async for session in get_session():
        query = (
            select(Email, ConnectedAccount)
            .join(ConnectedAccount)
            .where(
                ConnectedAccount.user_id == user.id,
                ConnectedAccount.status == "active",
            )
        )

        if account_id:
            query = query.where(ConnectedAccount.id == UUID(account_id))

        query = query.order_by(Email.date.desc()).limit(limit)

        result = await session.execute(query)
        rows = result.fetchall()

        result_list = [
            {
                "id": str(email.id),
                "account_id": str(email.account_id),
                "account_email": account.email_address,
                "subject": email.subject,
                "sender": email.sender,
                "recipients": email.recipients,
                "date": email.date.isoformat() if email.date else None,
                "snippet": email.snippet,
                "labels": email.labels or [],
            }
            for email, account in rows
        ]
        break
    return result_list
