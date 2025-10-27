from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_generate_covers_requires_video_file():
    resp = client.post("/api/creative/covers", data={"title": "示例标题"})
    # Missing required file should be a validation error
    assert resp.status_code == 422

