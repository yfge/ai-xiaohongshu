"""Schemas for agent run observability endpoints."""
from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field
from app.schemas.marketing import GeneratedImage, PromptVariant


class AgentRun(BaseModel):
    agent_id: str = Field(..., description="Agent identifier")
    request_id: str = Field(..., description="Unique execution request id")
    status: str = Field(..., description="Execution status")
    duration_ms: float = Field(..., description="Execution time in milliseconds")
    input_hash: str = Field(..., description="Hash of the input payload")
    prompt_count: int = Field(..., description="Number of prompts produced")
    image_count: int = Field(..., description="Number of images produced")
    error: str | None = Field(default=None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional structured metadata"
    )
    created_at: str = Field(..., description="ISO-8601 timestamp")


class AgentRunListResponse(BaseModel):
    runs: List[AgentRun]
    total: int
    limit: int
    offset: int


class AgentRunDetailResponse(BaseModel):
    run: AgentRun
    prompts: List[PromptVariant]
    images: List[GeneratedImage]
