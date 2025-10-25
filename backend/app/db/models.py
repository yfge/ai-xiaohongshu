"""SQLAlchemy ORM models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AgentRun(Base):
    """Persistent representation of an agent execution."""

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    prompt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class AgentRunPrompt(Base):
    """Prompt details generated during an agent run."""

    __tablename__ = "agent_run_prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class AgentRunImage(Base):
    """Image generation details associated with an agent run and optional prompt."""

    __tablename__ = "agent_run_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    prompt_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("agent_run_prompts.id", ondelete="SET NULL"), index=True, nullable=True
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_base64: Mapped[str | None] = mapped_column(Text, nullable=True)
    size: Mapped[str | None] = mapped_column(String(32), nullable=True)


class AuditLog(Base):
    """Audit log entries for API requests."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(8), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    req_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    res_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class ApiKey(Base):
    """API key storage for external access (SQL-backed)."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    prefix: Mapped[str] = mapped_column(String(24), nullable=False, unique=True, index=True)
    hashed_key: Mapped[str] = mapped_column(String(64), nullable=False)
    scopes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
