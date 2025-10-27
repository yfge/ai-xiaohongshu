"""FastAPI application entrypoint for the AI Xiaohongshu backend."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.routes import api_router
from app.core.config import get_settings
from app.services.audit import AuditRecord
from app.deps import get_audit_logger
from app.security import ApiKeyStore, SQLApiKeyStore
from app.db.session import get_session_maker
from app.services.rate_limit import RateLimiter, RateConfig

# Global limiter instance to ensure persistence across requests in tests and dev
_global_rate_limiter: RateLimiter | None = None
_global_rate_cfg: tuple[int, int] | None = None

app = FastAPI(title="AI Xiaohongshu API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


class HealthResponse(BaseModel):
    status: str = "ok"


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """Return service health information for monitoring and load-balancers."""
    return HealthResponse()


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Use settings override in tests if present
    settings_override = request.app.dependency_overrides.get(get_settings) if hasattr(request.app, "dependency_overrides") else None  # type: ignore[attr-defined]
    settings = settings_override() if callable(settings_override) else get_settings()

    # Only enforce for API key calls
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return await call_next(request)

    # Verify key minimally to ensure validity (supports JSONL or SQL stores)
    rec = None
    if settings.database_url:
        try:
            store = SQLApiKeyStore(get_session_maker(settings))
            rec = await store.verify_key(api_key)
        except Exception:
            rec = None
    if rec is None:
        store = ApiKeyStore(settings.api_key_store_path)
        rec = store.verify_key(api_key)
    if not rec:
        # Let route dependency handle invalid key for consistent error
        return await call_next(request)

    global _global_rate_limiter, _global_rate_cfg
    desired_cfg = (int(settings.api_key_rate_window_seconds), int(settings.api_key_rate_max_requests))
    if _global_rate_limiter is None or _global_rate_cfg != desired_cfg:
        _global_rate_limiter = RateLimiter(
            RateConfig(window_seconds=desired_cfg[0], max_requests=desired_cfg[1])
        )
        _global_rate_cfg = desired_cfg

    # Use raw API key string as bucket id
    if not _global_rate_limiter.allow(api_key):  # type: ignore[union-attr]
        from fastapi import Response

        return Response(status_code=429, content="Too Many Requests")

    return await call_next(request)


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    # Respect dependency override for get_settings in tests
    settings_override = request.app.dependency_overrides.get(get_settings) if hasattr(request.app, "dependency_overrides") else None  # type: ignore[attr-defined]
    settings = settings_override() if callable(settings_override) else get_settings()
    logger = get_audit_logger(settings)
    # Correlation id
    request_id = request.headers.get("x-request-id")
    if not request_id:
        import uuid
        request_id = uuid.uuid4().hex
    # Measure duration
    import time as _t
    started = _t.perf_counter()
    response = await call_next(request)
    elapsed_ms = (_t.perf_counter() - started) * 1000.0
    actor = getattr(request.state, "actor", None) or {"type": "anonymous", "id": "-"}
    try:
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent")
        rid = request_id or "-"
        # Sizes
        req_bytes = None
        try:
            cl = request.headers.get("content-length")
            if cl is not None:
                req_bytes = int(cl)
        except Exception:
            req_bytes = None
        res_bytes = None
        try:
            res_cl = response.headers.get("content-length")
            if res_cl is not None:
                res_bytes = int(res_cl)
        except Exception:
            res_bytes = None
        record = AuditRecord(
            actor_type=str(actor.get("type")),
            actor_id=str(actor.get("id")),
            request_id=rid,
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            ip=ip,
            user_agent=ua,
            metadata={
                "duration_ms": elapsed_ms,
                "req_bytes": req_bytes,
                "res_bytes": res_bytes,
            },
        )
        # Fire-and-forget; ensure awaited to satisfy async contract
        await logger.log(record)
    except Exception:
        # Never block or crash request due to audit failure
        pass
    # Propagate request id to client
    try:
        response.headers["X-Request-Id"] = request_id
    except Exception:
        pass
    return response
