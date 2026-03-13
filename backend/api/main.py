from __future__ import annotations

import time
from uuid import uuid4

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware

from ..worker.config import load_settings
from ..worker.utils.logger import log_event
from .routes.chat import router as chat_router
from .routes.ops import router as ops_router
from .routes.requests import router as requests_router

app = FastAPI(title="Cotai API", version="0.1.0")
settings = load_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    started_at = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001
        log_event(
            settings,
            "ERROR",
            "HTTP request failed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            error=str(exc),
        )
        raise

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    response.headers["X-Request-Id"] = request_id
    log_event(
        settings,
        "INFO",
        "HTTP request completed",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(chat_router)
app.include_router(ops_router)
app.include_router(requests_router)
