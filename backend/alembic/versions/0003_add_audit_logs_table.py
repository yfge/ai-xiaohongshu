"""create audit logs table

Revision ID: 0003_add_audit_logs_table
Revises: 0002_add_agent_run_details
Create Date: 2025-10-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_add_audit_logs_table"
down_revision = "0002_add_agent_run_details"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_type", sa.String(length=32), nullable=False, index=True),
        sa.Column("actor_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("request_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("method", sa.String(length=8), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False, index=True),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")

