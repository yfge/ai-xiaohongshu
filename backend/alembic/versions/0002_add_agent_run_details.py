"""add prompt and image details tables

Revision ID: 0002_add_agent_run_details
Revises: 0001_create_agent_runs_table
Create Date: 2025-10-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_add_agent_run_details"
down_revision = "0001_create_agent_runs_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_run_prompts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_run_id", sa.Integer(), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("idx", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("hashtags", sa.JSON(), nullable=True),
    )

    op.create_table(
        "agent_run_images",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_run_id", sa.Integer(), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("prompt_id", sa.Integer(), sa.ForeignKey("agent_run_prompts.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("idx", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("image_base64", sa.Text(), nullable=True),
        sa.Column("size", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("agent_run_images")
    op.drop_table("agent_run_prompts")

