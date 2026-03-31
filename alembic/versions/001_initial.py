"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-31

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("idx_api_keys_user", "api_keys", ["user_id"])

    op.create_table(
        "connected_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("email_address", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255)),
        sa.Column("access_token_encrypted", sa.Text, nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text),
        sa.Column("token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("sync_status", sa.String(20), default="pending"),
        sa.Column("sync_cursor", sa.Text),
        sa.Column("sync_error", sa.Text),
        sa.Column("emails_synced", sa.Integer, default=0),
        sa.Column("last_sync_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "email_address"),
    )
    op.create_index("idx_accounts_user", "connected_accounts", ["user_id"])

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stripe_subscription_id", sa.String(255), unique=True),
        sa.Column("stripe_customer_id", sa.String(255)),
        sa.Column("tier", sa.String(20), nullable=False, default="basic"),
        sa.Column("status", sa.String(20), nullable=False, default="inactive"),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    op.create_table(
        "emails",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("connected_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_message_id", sa.String(255), nullable=False),
        sa.Column("thread_id", sa.String(255)),
        sa.Column("subject", sa.Text),
        sa.Column("sender", sa.String(255)),
        sa.Column("recipients", sa.Text),
        sa.Column("date", sa.DateTime(timezone=True)),
        sa.Column("snippet", sa.Text),
        sa.Column("labels", sa.Text, default=""),
        sa.Column("embedding", sa.Text, default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint("account_id", "provider_message_id"),
    )
    op.create_index("idx_emails_account", "emails", ["account_id"])
    op.create_index("idx_emails_date", "emails", ["date"])


def downgrade() -> None:
    op.drop_table("emails")
    op.drop_table("subscriptions")
    op.drop_table("connected_accounts")
    op.drop_table("api_keys")
    op.drop_table("users")
