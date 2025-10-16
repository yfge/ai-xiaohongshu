"""Integration tests for the backend health endpoint."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.anyio("asyncio")
async def test_health_endpoint_returns_ok() -> None:
    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
