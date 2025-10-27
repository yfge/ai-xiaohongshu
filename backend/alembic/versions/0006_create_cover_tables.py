"""create tables for cover generation presets and jobs

Revision ID: 0006_create_cover_tables
Revises: 0005_extend_audit_logs_with_metrics
Create Date: 2025-10-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_create_cover_tables"
down_revision = "0005_extend_audit_logs_with_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fonts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family", sa.String(length=100), nullable=False, index=True),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("license", sa.String(length=64), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
    )

    op.create_table(
        "cover_style_presets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=64), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("style_type", sa.String(length=16), nullable=False),  # glass|gradient|sticker
        sa.Column("title_font_id", sa.Integer(), sa.ForeignKey("fonts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("subtitle_font_id", sa.Integer(), sa.ForeignKey("fonts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("safe_margin_pct", sa.Float(), nullable=True),
        sa.Column("padding_pct", sa.Float(), nullable=True),
        sa.Column("palette_start", sa.String(length=16), nullable=True),
        sa.Column("palette_end", sa.String(length=16), nullable=True),
        sa.Column("shadow", sa.Boolean(), nullable=True),
        sa.Column("sticker_default_text", sa.String(length=24), nullable=True),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
    )

    op.create_table(
        "cover_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("actor_type", sa.String(length=32), nullable=False, index=True),
        sa.Column("actor_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("subtitle", sa.String(length=200), nullable=True),
        sa.Column("style_key", sa.String(length=64), nullable=True, index=True),
        sa.Column("preset_id", sa.Integer(), sa.ForeignKey("cover_style_presets.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("sticker_text", sa.String(length=24), nullable=True),
        sa.Column("video_ref", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="succeeded"),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("result_9x16_url", sa.String(length=512), nullable=True),
        sa.Column("result_3x4_url", sa.String(length=512), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("score_meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
    )

    op.create_table(
        "cover_job_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("cover_jobs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("frame_index", sa.Integer(), nullable=True),
        sa.Column("brightness", sa.Float(), nullable=True),
        sa.Column("laplacian_var", sa.Float(), nullable=True),
        sa.Column("entropy", sa.Float(), nullable=True),
        sa.Column("subtitle_penalty", sa.Float(), nullable=True),
        sa.Column("face_area", sa.Float(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("cover_job_scores")
    op.drop_table("cover_jobs")
    op.drop_table("cover_style_presets")
    op.drop_table("fonts")

