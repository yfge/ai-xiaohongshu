"""FastAPI dependency helpers."""
from __future__ import annotations

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.marketing import MarketingCollageService


def get_marketing_service(
    settings: Settings = Depends(get_settings),
) -> MarketingCollageService:
    """Provide a marketing collage service instance per request."""

    return MarketingCollageService(settings)
