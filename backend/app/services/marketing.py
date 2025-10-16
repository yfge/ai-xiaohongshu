"""Business workflow for generating Xiaohongshu marketing collages."""
from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from pydantic import ValidationError
from volcenginesdkarkruntime import AsyncArk

from app.core.config import Settings
from app.schemas.marketing import (
    GeneratedImage,
    MarketingGenerationResponse,
    PromptGenerationPayload,
    PromptVariant,
)
from app.services.ark_client import async_ark_client

logger = logging.getLogger(__name__)


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

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def generate_collage(
        self,
        *,
        brief: str,
        count: int,
        uploaded_images: Sequence[UploadedImage],
    ) -> MarketingGenerationResponse:
        self._ensure_credentials()
        self._validate_inputs(count=count, images=uploaded_images)

        async with async_ark_client(self._settings) as client:
            prompt_variants = await self._generate_prompt_variants(
                client=client,
                brief=brief,
                count=count,
                images=uploaded_images,
            )
            image_results = await self._generate_images(
                client=client,
                prompt_variants=prompt_variants,
                images=uploaded_images,
            )

        return MarketingGenerationResponse(
            prompts=prompt_variants,
            images=image_results,
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
        })

        response = await client.chat.completions.create(
            model=self._settings.ark_prompt_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=self._settings.ark_prompt_temperature,
            max_tokens=self._settings.ark_prompt_max_tokens,
            response_format={"type": "json_object"},
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
    ) -> List[GeneratedImage]:
        base64_imgs = [image.to_data_uri() for image in images]
        results: List[GeneratedImage] = []

        for variant in prompt_variants:
            logger.debug(
                "Generating image via Ark", extra={
                    "image_model": self._settings.ark_image_model,
                    "prompt": variant.prompt,
                }
            )
            resp = await client.images.generate(
                model=self._settings.ark_image_model,
                prompt=variant.prompt,
                image=base64_imgs,
                response_format="b64_json",
                size=self._settings.ark_image_size,
            )

            if not resp.data:
                raise ArkServiceError("Ark 未返回生成图像数据")

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

        return results
