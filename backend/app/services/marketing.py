"""Business workflow for generating Xiaohongshu marketing collages."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Sequence, Tuple, TypeVar
from uuid import uuid4

from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.marketing import (
    GeneratedImage,
    MarketingGenerationResponse,
    PromptGenerationPayload,
    PromptVariant,
)
from app.services.ark_client import async_ark_client
from app.services.agent_runs import AgentRunRecord, AgentRunRecorder

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ArkConfigurationError(RuntimeError):
    """Raised when Ark credentials are not configured."""


class ArkServiceError(RuntimeError):
    """Raised when Ark runtime returns an unexpected result."""


@dataclass(slots=True)
class UploadedImage:
    """In-memory representation of an uploaded asset."""

    filename: str
    content_type: str | None
    data: bytes

    def to_data_uri(self) -> str:
        """Convert payload to a base64 data URI accepted by Ark."""

        if not self.data:
            raise ArkServiceError(f"Image {self.filename} is empty")

        media_type = (self.content_type or "image/png").split(";")[0]
        encoded = base64.b64encode(self.data).decode("ascii")
        return f"data:{media_type};base64,{encoded}"


class MarketingCollageService:
    """Coordinate prompt + image generation via Ark runtime."""

    def __init__(
        self, settings: Settings, *, recorder: AgentRunRecorder | None = None
    ) -> None:
        self._settings = settings
        self._recorder = recorder

    async def generate_collage(
        self,
        *,
        brief: str,
        count: int,
        uploaded_images: Sequence[UploadedImage],
    ) -> MarketingGenerationResponse:
        request_id = uuid4().hex
        logger.info(
            "Starting collage generation",
            extra={
                "agent_id": "CollageAgent",
                "request_id": request_id,
                "count": count,
                "image_count": len(uploaded_images),
            },
        )

        self._ensure_credentials()
        self._validate_inputs(count=count, images=uploaded_images)

        prompt_variants: List[PromptVariant] = []
        image_results: List[GeneratedImage] = []
        failed_images: List[PromptVariant] = []
        timings: dict[str, float] = {}
        status = "success"
        error_message: str | None = None
        started_at = time.perf_counter()

        try:
            async with async_ark_client(self._settings) as client:
                prompt_started = time.perf_counter()
                prompt_variants = await self._generate_prompt_variants(
                    client=client,
                    brief=brief,
                    count=count,
                    images=uploaded_images,
                    request_id=request_id,
                )
                timings["prompt_ms"] = (time.perf_counter() - prompt_started) * 1000

                image_started = time.perf_counter()
                image_results, failed_images = await self._generate_images(
                    client=client,
                    prompt_variants=prompt_variants,
                    images=uploaded_images,
                    request_id=request_id,
                )
                timings["image_ms"] = (time.perf_counter() - image_started) * 1000
        except Exception as exc:
            status = "failed"
            error_message = str(exc)
            logger.exception(
                "Collage generation failed",
                extra={
                    "agent_id": "CollageAgent",
                    "request_id": request_id,
                    "count": count,
                },
            )
            raise
        else:
            logger.info(
                "Collage generation completed",
                extra={
                    "agent_id": "CollageAgent",
                    "request_id": request_id,
                    "prompt_count": len(prompt_variants),
                    "image_count": len(image_results),
                    "failed_image_count": len(failed_images),
                    "timings_ms": timings,
                },
            )
            return MarketingGenerationResponse(
                prompts=prompt_variants,
                images=image_results,
            )
        finally:
            await self._record_agent_run(
                brief=brief,
                count=count,
                uploaded_images=uploaded_images,
                request_id=request_id,
                status=status,
                prompt_variants=prompt_variants,
                image_results=image_results,
                failed_image_variants=failed_images,
                error=error_message,
                duration_ms=(time.perf_counter() - started_at) * 1000,
                timings=timings,
            )

    def _ensure_credentials(self) -> None:
        if not (
            self._settings.ark_api_key
            or (self._settings.ark_ak and self._settings.ark_sk)
        ):
            raise ArkConfigurationError(
                "Missing Ark credentials. Configure ARK_API_KEY or ARK_AK/ARK_SK."
            )

    def _validate_inputs(
        self, *, count: int, images: Sequence[UploadedImage]
    ) -> None:
        if count <= 0:
            raise ArkServiceError("生成数量必须大于 0")
        if count > self._settings.ark_prompt_max_count:
            raise ArkServiceError(
                f"生成数量不能超过 {self._settings.ark_prompt_max_count}"
            )
        if not images:
            raise ArkServiceError("请至少上传一张参考图片")

    async def _generate_prompt_variants(
        self,
        *,
        client: AsyncArk,
        brief: str,
        count: int,
        images: Sequence[UploadedImage],
        request_id: str,
    ) -> List[PromptVariant]:
        system_prompt = self._settings.ark_prompt_template.format(count=count)
        format_instructions = self._settings.ark_prompt_format_instructions
        image_parts = [
            {
                "type": "image_url",
                "image_url": {"url": image.to_data_uri()},
            }
            for image in images
        ]
        user_content: List[dict] = [
            {
                "type": "text",
                "text": (
                    "参考提示词：\n"
                    f"{brief.strip()}\n\n"
                    "请根据上述提示词和上传的图片生成灵感。\n"
                    f"输出要求：\n{format_instructions}"
                ),
            }
        ] + image_parts

        logger.debug("Submitting prompt generation request to Ark", extra={
            "prompt_model": self._settings.ark_prompt_model,
            "count": count,
            "image_count": len(images),
            "request_id": request_id,
        })

        response = await self._execute_with_retries(
            lambda: client.chat.completions.create(
                model=self._settings.ark_prompt_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=self._settings.ark_prompt_temperature,
                max_tokens=self._settings.ark_prompt_max_tokens,
                response_format={"type": "json_object"},
            ),
            operation="prompt_generation",
            request_id=request_id,
        )

        if not response.choices:
            raise ArkServiceError("Ark 未返回任何提示词结果")

        content = response.choices[0].message.content
        if not content:
            raise ArkServiceError("Ark 返回内容为空")

        try:
            payload = PromptGenerationPayload.model_validate_json(content)
        except (ValidationError, json.JSONDecodeError) as exc:
            logger.exception("Failed to parse Ark prompt payload: %s", content)
            raise ArkServiceError("无法解析 Ark 返回的提示词 JSON") from exc

        prompts = payload.prompts
        if len(prompts) != count:
            logger.warning(
                "Prompt count mismatch", extra={
                    "expected": count,
                    "actual": len(prompts),
                }
            )
            if len(prompts) < count:
                raise ArkServiceError("Ark 返回的提示词数量不足")
            prompts = prompts[:count]

        return prompts

    async def _generate_images(
        self,
        *,
        client: AsyncArk,
        prompt_variants: Sequence[PromptVariant],
        images: Sequence[UploadedImage],
        request_id: str,
    ) -> Tuple[List[GeneratedImage], List[PromptVariant]]:
        base64_imgs = [image.to_data_uri() for image in images]
        results: List[GeneratedImage] = []
        failed_variants: List[PromptVariant] = []

        for variant in prompt_variants:
            logger.debug(
                "Generating image via Ark", extra={
                    "image_model": self._settings.ark_image_model,
                    "prompt": variant.prompt,
                    "request_id": request_id,
                }
            )
            try:
                resp = await self._execute_with_retries(
                    lambda variant=variant: client.images.generate(
                        model=self._settings.ark_image_model,
                        prompt=variant.prompt,
                        image=base64_imgs,
                        response_format="b64_json",
                        size=self._settings.ark_image_size,
                    ),
                    operation="image_generation",
                    request_id=request_id,
                )
            except ArkServiceError as exc:
                failed_variants.append(variant)
                logger.error(
                    "Ark image generation failed after retries",
                    extra={
                        "agent_id": "CollageAgent",
                        "request_id": request_id,
                        "prompt_title": variant.title,
                    },
                    exc_info=exc,
                )
                continue

            if not resp.data:
                failed_variants.append(variant)
                logger.warning(
                    "Ark 未返回生成图像数据",
                    extra={
                        "agent_id": "CollageAgent",
                        "request_id": request_id,
                        "prompt_title": variant.title,
                    },
                )
                continue

            first_image = resp.data[0]
            image_url = first_image.url or None
            b64_json = first_image.b64_json or None
            results.append(
                GeneratedImage(
                    prompt=variant,
                    image_url=image_url,
                    image_base64=b64_json,
                    size=first_image.size or self._settings.ark_image_size,
                )
            )

        if not results:
            raise ArkServiceError("Ark 图像生成全部失败，请稍后重试")

        if failed_variants:
            logger.warning(
                "Ark image generation completed with partial failures",
                extra={
                    "agent_id": "CollageAgent",
                    "request_id": request_id,
                    "failed_prompts": [variant.title for variant in failed_variants],
                },
            )

        return results, failed_variants

    async def _record_agent_run(
        self,
        *,
        brief: str,
        count: int,
        uploaded_images: Sequence[UploadedImage],
        request_id: str,
        status: str,
        prompt_variants: Sequence[PromptVariant],
        image_results: Sequence[GeneratedImage],
        failed_image_variants: Sequence[PromptVariant],
        error: str | None,
        duration_ms: float,
        timings: dict[str, float],
    ) -> None:
        if not self._recorder:
            return

        input_hash = self._compute_input_hash(brief=brief, images=uploaded_images)
        record = AgentRunRecord(
            agent_id="CollageAgent",
            request_id=request_id,
            status=status,
            duration_ms=duration_ms,
            input_hash=input_hash,
            prompt_count=len(prompt_variants),
            image_count=len(image_results),
            error=error,
            metadata={
                "prompt_ms": timings.get("prompt_ms"),
                "image_ms": timings.get("image_ms"),
                "count": count,
                "prompt_model": self._settings.ark_prompt_model,
                "image_model": self._settings.ark_image_model,
                "failed_prompts": [variant.title for variant in failed_image_variants],
                "retry_attempts": self._settings.ark_retry_attempts,
            },
        )

        # If the recorder supports details, persist prompts/images atomically
        if hasattr(self._recorder, "record_details"):
            try:
                await getattr(self._recorder, "record_details")(  # type: ignore[misc]
                    record,
                    prompts=list(prompt_variants),
                    images=list(image_results),
                )
                return
            except Exception:  # pragma: no cover - defensive, fallback to summary
                logger.exception("Recording details failed; falling back to summary record")

        await self._recorder.record(record)

    def _compute_input_hash(
        self, *, brief: str, images: Sequence[UploadedImage]
    ) -> str:
        hasher = hashlib.sha256()
        hasher.update(brief.strip().encode("utf-8"))
        for image in images:
            hasher.update(image.data)
        return hasher.hexdigest()

    async def _execute_with_retries(
        self,
        task: Callable[[], Awaitable[T]],
        *,
        operation: str,
        request_id: str,
    ) -> T:
        attempts = self._settings.ark_retry_attempts
        backoff = self._settings.ark_retry_backoff_seconds
        last_error: Exception | None = None

        for attempt in range(attempts + 1):
            try:
                return await asyncio.wait_for(
                    task(), timeout=self._settings.ark_request_timeout
                )
            except Exception as exc:  # pragma: no cover - defensive guard
                last_error = exc
                if attempt == attempts:
                    break

                wait_seconds = backoff * (attempt + 1)
                logger.warning(
                    "Ark %s attempt %s failed, retrying",
                    operation,
                    attempt + 1,
                    extra={
                        "agent_id": "CollageAgent",
                        "request_id": request_id,
                        "operation": operation,
                        "retry_after_s": wait_seconds,
                    },
                    exc_info=exc,
                )
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)

        error_message = f"Ark {operation} 调用失败"
        if request_id:
            error_message = f"{error_message} (request_id={request_id})"
        raise ArkServiceError(error_message) from last_error
