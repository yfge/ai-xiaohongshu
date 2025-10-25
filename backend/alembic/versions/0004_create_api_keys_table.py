"""create api keys table

Revision ID: 0004_create_api_keys_table
Revises: 0003_add_audit_logs_table
Create Date: 2025-10-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_create_api_keys_table"
down_revision = "0003_add_audit_logs_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("prefix", sa.String(length=24), nullable=False, index=True, unique=True),
        sa.Column("hashed_key", sa.String(length=64), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("api_keys")

