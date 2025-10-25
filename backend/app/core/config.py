"""Application-wide settings and Ark client configuration helpers."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 保留历史模板供参考，便于回溯旧版提示词策略
LEGACY_PROMPT_TEMPLATE_REFERENCE = (
    "你是一名资深的小红书营销创意总监。结合运营给出的营销提示词与上传的参考素材，"
    "生成 {count} 个适合小红书图文/组图的 Midjourney/SD 风格提示词。每个提示词需要强调"
    "商品卖点、内容氛围以及适合的镜头语言。请严格按照 JSON 结构返回，"
    "并确保 `prompts` 列表长度等于 {count}。"
)

DEFAULT_PROMPT_TEMPLATE = (
    "你是一名专注种草营销的创意总监，需要用中文写出具备故事性与画面感的提示词。结合运营给出的营销"
    "提示词和上传的参考素材，生成 {count} 个详细的视觉创意描述。每条提示词需包含：场景氛围、主角造型、"
    "商品卖点、镜头语言与辅助道具，并明确强调种草话术和消费动机。所有内容使用中文，体现情绪张力与"
    "生活方式。"
)

DEFAULT_PROMPT_FORMAT_INSTRUCTIONS = (
    "输出 JSON 对象，字段说明如下：\n"
    "- prompts: 提示词数组\n"
    "- prompts[].title: 20 字内的中文主题名称，需突出种草场景\n"
    "- prompts[].prompt: 以 2-3 句完整中文描述呈现营销画面，包含场景氛围、人物/商品细节及种草利益点\n"
    "- prompts[].description: 补充该创意适合的传播话术或运营要点\n"
    "- prompts[].hashtags: 3-5 个小红书常用中文话题标签（不带 #）"
)


class Settings(BaseSettings):
    """Global application configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ark_api_key: Optional[str] = Field(default=None, env="ARK_API_KEY")
    ark_ak: Optional[str] = Field(default=None, env="ARK_AK")
    ark_sk: Optional[str] = Field(default=None, env="ARK_SK")
    ark_base_url: str = Field(
        default="https://ark.cn-beijing.volces.com/api/v3", env="ARK_BASE_URL"
    )
    ark_prompt_model: str = Field(
        default="ep-20240620000000-prompt-creation", env="ARK_PROMPT_MODEL"
    )
    ark_image_model: str = Field(
        default="ep-20240620000000-image-creation", env="ARK_IMAGE_MODEL"
    )
    ark_prompt_template: str = Field(
        default=DEFAULT_PROMPT_TEMPLATE, env="ARK_PROMPT_TEMPLATE"
    )
    ark_prompt_format_instructions: str = Field(
        default=DEFAULT_PROMPT_FORMAT_INSTRUCTIONS,
        env="ARK_PROMPT_FORMAT_INSTRUCTIONS",
    )
    ark_prompt_temperature: float = Field(default=0.6, env="ARK_PROMPT_TEMPERATURE")
    ark_prompt_max_tokens: int = Field(default=800, env="ARK_PROMPT_MAX_TOKENS")
    ark_prompt_max_count: int = Field(default=6, env="ARK_PROMPT_MAX_COUNT")
    ark_image_size: str = Field(default="1024x1024", env="ARK_IMAGE_SIZE")
    ark_request_timeout: float = Field(default=120.0, env="ARK_REQUEST_TIMEOUT")
    ark_retry_attempts: int = Field(default=2, env="ARK_RETRY_ATTEMPTS")
    ark_retry_backoff_seconds: float = Field(
        default=1.5, env="ARK_RETRY_BACKOFF_SECONDS"
    )
    collage_allowed_mime_prefixes: tuple[str, ...] = Field(
        default=("image/",), env="COLLAGE_ALLOWED_MIME_PREFIXES"
    )
    collage_upload_max_bytes: int = Field(
        default=5 * 1024 * 1024, env="COLLAGE_UPLOAD_MAX_BYTES"
    )
    agent_run_store_path: str = Field(
        default="storage/agent_runs.jsonl", env="AGENT_RUN_STORE_PATH"
    )
    database_url: Optional[str] = Field(default=None, env="DATABASE_URL")
    database_echo: bool = Field(default=False, env="DATABASE_ECHO")
    # Basic auth for admin endpoints (optional)
    auth_basic_username: Optional[str] = Field(default=None, env="AUTH_BASIC_USERNAME")
    auth_basic_password_hash: Optional[str] = Field(
        default=None, env="AUTH_BASIC_PASSWORD_HASH"
    )
    auth_basic_password_plain: Optional[str] = Field(
        default=None, env="AUTH_BASIC_PASSWORD_PLAIN"
    )
    # Stores for API keys and audit logs (JSONL fallback)
    api_key_store_path: str = Field(
        default="storage/api_keys.jsonl", env="API_KEY_STORE_PATH"
    )
    audit_log_store_path: str = Field(
        default="storage/audit_logs.jsonl", env="AUDIT_LOG_STORE_PATH"
    )
    # API key rate limiting
    api_key_rate_window_seconds: int = Field(
        default=60, env="API_KEY_RATE_WINDOW_SECONDS"
    )
    api_key_rate_max_requests: int = Field(
        default=60, env="API_KEY_RATE_MAX_REQUESTS"
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()


__all__ = ["Settings", "get_settings"]
