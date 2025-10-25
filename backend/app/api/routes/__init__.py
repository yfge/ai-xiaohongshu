"""API route registrations."""
from fastapi import APIRouter

from app.api.routes import agent_runs, marketing, auth, admin, external


api_router = APIRouter()
api_router.include_router(marketing.router)
api_router.include_router(agent_runs.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(external.router)

__all__ = ["api_router"]
