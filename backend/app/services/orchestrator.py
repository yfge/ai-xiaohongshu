"""Lightweight orchestrator skeleton for composing agent workflows."""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List
from uuid import uuid4

from app.services.agent_runs import AgentRunRecord, AgentRunRecorder

logger = logging.getLogger(__name__)


AgentHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


@dataclass(slots=True)
class OrchestratorStep:
    """Definition of a single agent execution within a workflow."""

    agent_id: str
    handler: AgentHandler


class AgentOrchestrator:
    """Minimal orchestrator supporting sequential agent execution."""

    def __init__(self, *, recorder: AgentRunRecorder | None = None) -> None:
        self._recorder = recorder
        self._steps: List[OrchestratorStep] = []

    def register(self, *, agent_id: str, handler: AgentHandler) -> None:
        """Register an agent handler that will run in order of registration."""

        self._steps.append(OrchestratorStep(agent_id=agent_id, handler=handler))

    async def run(self, initial_context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the configured workflow and return the aggregated context."""

        context = dict(initial_context)
        for index, step in enumerate(self._steps):
            step_request_id = uuid4().hex
            step_started = time.perf_counter()
            status = "success"
            error_message: str | None = None
            before_context = dict(context)

            logger.info(
                "Starting agent step",
                extra={
                    "agent_id": step.agent_id,
                    "request_id": step_request_id,
                    "step_index": index,
                    "context_keys": list(before_context.keys()),
                },
            )

            try:
                result = await step.handler(before_context)
            except Exception as exc:  # pragma: no cover - defensive orchestration guard
                status = "failed"
                error_message = str(exc)
                logger.exception(
                    "Agent step failed",
                    extra={
                        "agent_id": step.agent_id,
                        "request_id": step_request_id,
                        "step_index": index,
                    },
                )
                await self._record_step(
                    agent_id=step.agent_id,
                    request_id=step_request_id,
                    status=status,
                    before_context=before_context,
                    result={},
                    duration_ms=(time.perf_counter() - step_started) * 1000,
                    error=error_message,
                )
                raise

            context[step.agent_id] = result

            await self._record_step(
                agent_id=step.agent_id,
                request_id=step_request_id,
                status=status,
                before_context=before_context,
                result=result,
                duration_ms=(time.perf_counter() - step_started) * 1000,
                error=error_message,
            )

            logger.info(
                "Agent step completed",
                extra={
                    "agent_id": step.agent_id,
                    "request_id": step_request_id,
                    "step_index": index,
                    "duration_ms": (time.perf_counter() - step_started) * 1000,
                },
            )

        return context

    async def _record_step(
        self,
        *,
        agent_id: str,
        request_id: str,
        status: str,
        before_context: Dict[str, Any],
        result: Dict[str, Any],
        duration_ms: float,
        error: str | None,
    ) -> None:
        if not self._recorder:
            return

        input_hash = _hash_context(before_context)
        record = AgentRunRecord(
            agent_id=agent_id,
            request_id=request_id,
            status=status,
            duration_ms=duration_ms,
            input_hash=input_hash,
            prompt_count=_safe_len(result.get("prompts")),
            image_count=_safe_len(result.get("images")),
            error=error,
            metadata={
                "result_keys": list(result.keys()),
                "context_keys": list(before_context.keys()),
            },
        )
        await self._recorder.record(record)


def _hash_context(context: Dict[str, Any]) -> str:
    serialized = json.dumps(context, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _safe_len(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    return 0


__all__ = ["AgentOrchestrator", "AgentHandler", "OrchestratorStep"]
