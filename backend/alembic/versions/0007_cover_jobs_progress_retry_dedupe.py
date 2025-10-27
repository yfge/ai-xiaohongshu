"""add progress/retry/dedupe fields to cover_jobs

Revision ID: 0007_cover_jobs_progress_retry_dedupe
Revises: 0006_create_cover_tables
Create Date: 2025-10-28
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_cover_jobs_progress_retry_dedupe"
down_revision = "0006_create_cover_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cover_jobs") as batch:
        batch.add_column(sa.Column("progress_pct", sa.Float(), nullable=True))
        batch.add_column(sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("dedupe_key", sa.String(length=128), nullable=True))
        batch.create_index("ix_cover_jobs_dedupe_key", ["dedupe_key"])  # type: ignore[arg-type]


def downgrade() -> None:
    with op.batch_alter_table("cover_jobs") as batch:
        batch.drop_index("ix_cover_jobs_dedupe_key")
        batch.drop_column("dedupe_key")
        batch.drop_column("started_at")
        batch.drop_column("max_attempts")
        batch.drop_column("attempts")
        batch.drop_column("progress_pct")

