import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import ConnectedAccount, Email, get_session, VectorEmbedding
from backend.interfaces.embedding_model import EmbeddingModel
from backend.interfaces.vector_store import VectorStore
from backend.oauth import PROVIDERS as OAUTH_PROVIDERS
from backend.email import PROVIDERS as EMAIL_PROVIDERS
from backend.embeddings import SentenceTransformersEmbedding
from backend.vector import SQLiteVectorStore

logger = logging.getLogger(__name__)

embedding_model: EmbeddingModel | None = None
vector_store: VectorStore | None = None


def get_embedding_model() -> EmbeddingModel:
    global embedding_model
    if embedding_model is None:
        embedding_model = SentenceTransformersEmbedding()
    return embedding_model


def get_vector_store() -> VectorStore:
    global vector_store
    if vector_store is None:
        vector_store = SQLiteVectorStore()
    return vector_store


def check_account_limit(tier: str | None, current_count: int) -> None:
    from backend.interfaces.payment_provider import TIER_LIMITS

    tier = tier or "free"
    limit = TIER_LIMITS.get(tier, 1)
    if current_count >= limit:
        raise PermissionError(
            f"Account limit reached for {tier} tier. Upgrade to connect more accounts."
        )


async def sync_account_emails(account_id: str | UUID) -> None:
    from backend.auth import decrypt_token
    from backend.database import SessionLocal

    db = SessionLocal()
    try:
        account = (
            db.query(ConnectedAccount)
            .filter(ConnectedAccount.id == str(account_id))
            .first()
        )
        if not account:
            return

        account.sync_status = "syncing"
        account.sync_error = None
        db.commit()

        try:
            access_token = decrypt_token(account.access_token_encrypted)
            oauth_provider = OAUTH_PROVIDERS.get(account.provider)
            email_provider = EMAIL_PROVIDERS.get(account.provider)

            if not oauth_provider or not email_provider:
                raise ValueError(f"Unknown provider: {account.provider}")

            emails = await email_provider.get_emails(access_token, max_results=50)

            for email_data in emails:
                msg_id = email_data.get("id")
                if not msg_id:
                    continue

                body = await email_provider.get_email_body(access_token, msg_id)
                content = f"{email_data.get('subject', '')}\n{email_data.get('from', '')}\n{body}"

                content_hash = hashlib.sha256(content.encode()).hexdigest()
                existing = (
                    db.query(Email)
                    .filter(
                        Email.account_id == account.id,
                        Email.provider_message_id == msg_id,
                    )
                    .first()
                )

                if not existing:
                    email = Email(
                        account_id=account.id,
                        provider_message_id=msg_id,
                        thread_id=email_data.get("thread_id"),
                        subject=email_data.get("subject", ""),
                        sender=email_data.get("from", ""),
                        recipients="",
                        date=datetime.now(timezone.utc),
                        snippet=email_data.get("snippet", ""),
                        body_hash=content_hash,
                    )
                    db.add(email)
                    db.commit()
                    db.refresh(email)

                    await index_email_content(account.id, msg_id, content, email.id)

            account.sync_status = "completed"
            account.emails_synced = (
                db.query(Email).filter(Email.account_id == account.id).count()
            )
            account.last_sync_at = datetime.now(timezone.utc)

        except Exception as e:
            account.sync_status = "failed"
            account.sync_error = str(e)
            logger.error(f"Sync failed for account {account_id}: {e}")

        db.commit()
    finally:
        db.close()


async def index_email_content(
    account_id: str, message_id: str, content: str, email_db_id: str
) -> None:
    try:
        model = get_embedding_model()
        vstore = get_vector_store()

        embedding = model.encode_query(content)

        await vstore.insert(
            id=f"{account_id}:{message_id}",
            embedding=embedding,
            metadata={
                "account_id": account_id,
                "message_id": message_id,
                "content_hash": hashlib.sha256(content.encode()).hexdigest(),
                "email_db_id": str(email_db_id),
            },
        )
    except Exception as e:
        logger.error(f"Failed to index email {message_id}: {e}")


async def incremental_sync(account_id: str | UUID) -> None:
    await sync_account_emails(account_id)


async def search_similar(
    session: AsyncSession, account_ids: list[UUID], query: str, limit: int = 10
) -> list[Email]:
    model = get_embedding_model()
    vstore = get_vector_store()

    query_embedding = model.encode_query(query)

    results = await vstore.search(
        query_embedding,
        limit=limit,
        filters={"account_id": str(account_ids[0]) if account_ids else None},
    )

    email_ids = []
    for r in results:
        metadata = r.get("metadata", {})
        email_db_id = metadata.get("email_db_id")
        if email_db_id:
            email_ids.append(UUID(email_db_id))

    if not email_ids:
        return []

    result = await session.execute(select(Email).where(Email.id.in_(email_ids)))
    return list(result.scalars().all())
