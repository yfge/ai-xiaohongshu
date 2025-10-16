"""API route registrations."""
from fastapi import APIRouter

from app.api.routes import marketing


api_router = APIRouter()
api_router.include_router(marketing.router)

__all__ = ["api_router"]
