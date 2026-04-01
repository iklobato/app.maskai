"""add_vector_embeddings

Revision ID: 6a17dee42721
Revises: 001
Create Date: 2026-03-31 21:07:02.565910

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6a17dee42721"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vector_embeddings",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("message_id", sa.String(255), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding_vector", sa.Text, nullable=False),
        sa.Column("metadata_json", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("idx_vector_account", "vector_embeddings", ["account_id"])


def downgrade() -> None:
    op.drop_table("vector_embeddings")
