"""Schemas for marketing collage workflow."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class PromptVariant(BaseModel):
    title: str = Field(..., description="短标题，展示提示词的营销角度")
    prompt: str = Field(..., description="可直接用于图像生成模型的提示词")
    description: str | None = Field(
        default=None, description="中文描述，说明图像创意与场景"
    )
    hashtags: List[str] = Field(
        default_factory=list, description="推荐的小红书话题标签"
    )


class PromptGenerationPayload(BaseModel):
    prompts: List[PromptVariant]


class GeneratedImage(BaseModel):
    prompt: PromptVariant
    image_url: str | None = Field(
        default=None, description="火山引擎返回的图像访问 URL"
    )
    image_base64: str | None = Field(
        default=None, description="Base64 字符串，可用于内嵌展示"
    )
    size: str | None = Field(default=None, description="生成的图像尺寸")


class MarketingGenerationResponse(BaseModel):
    prompts: List[PromptVariant]
    images: List[GeneratedImage]
