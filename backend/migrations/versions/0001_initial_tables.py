"""create initial profile kb chat tables

Revision ID: 0001_initial_tables
Revises:
Create Date: 2026-05-16 00:00:00.000000
"""

from typing import Sequence, Union

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0001_initial_tables"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE SCHEMA IF NOT EXISTS profile")
    op.execute("CREATE SCHEMA IF NOT EXISTS kb")
    op.execute("CREATE SCHEMA IF NOT EXISTS chat")

    op.create_table(
        "user_profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("user_id"),
        schema="profile",
    )
    op.create_table(
        "alumni_records",
        sa.Column("alumni_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_doc", sa.String(length=500), nullable=True),
        sa.Column("record_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("alumni_id"),
        schema="kb",
    )
    op.create_table(
        "conversations",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("messages", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("session_id"),
        schema="chat",
    )


def downgrade() -> None:
    op.drop_table("conversations", schema="chat")
    op.drop_table("alumni_records", schema="kb")
    op.drop_table("user_profiles", schema="profile")
    op.execute("DROP SCHEMA IF EXISTS chat")
    op.execute("DROP SCHEMA IF EXISTS kb")
    op.execute("DROP SCHEMA IF EXISTS profile")
