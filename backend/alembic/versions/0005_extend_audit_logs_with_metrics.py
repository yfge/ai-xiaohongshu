"""extend audit logs with metrics and metadata

Revision ID: 0005_extend_audit_logs_with_metrics
Revises: 0004_create_api_keys_table
Create Date: 2025-10-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_extend_audit_logs_with_metrics"
down_revision = "0004_create_api_keys_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("duration_ms", sa.Float(), nullable=True))
    op.add_column("audit_logs", sa.Column("req_bytes", sa.Integer(), nullable=True))
    op.add_column("audit_logs", sa.Column("res_bytes", sa.Integer(), nullable=True))
    op.add_column("audit_logs", sa.Column("metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_logs", "metadata")
    op.drop_column("audit_logs", "res_bytes")
    op.drop_column("audit_logs", "req_bytes")
    op.drop_column("audit_logs", "duration_ms")

