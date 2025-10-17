"""API route registrations."""
from fastapi import APIRouter

from app.api.routes import agent_runs, marketing


api_router = APIRouter()
api_router.include_router(marketing.router)
api_router.include_router(agent_runs.router)

__all__ = ["api_router"]
