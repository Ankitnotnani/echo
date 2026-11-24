"""FastAPI app: exactly three endpoints, JSON everywhere, no stack traces."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .config import Settings, load_settings
from .db import Database, utc_now_iso
from .gateway import AllProvidersUnavailable, LLMGateway
from .schemas import ChatRequest, ChatResponse
from .simulation import parse_simulation_header

logger = logging.getLogger("echo")


def create_app(settings: Optional[Settings] = None, gateway: Optional[LLMGateway] = None) -> FastAPI:
    settings = settings or load_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db = Database(settings.database_path)
    gw = gateway or LLMGateway(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        db.init()
        gw.setup_cache()
        if len(gw.slots) < 2:
            logger.warning("Only %d API key(s) configured; the assignment expects at least 2", len(gw.slots))
        logger.info("Started: %r, cache=%s, simulation=%s", settings, gw.cache_type, settings.enable_failure_simulation)
        yield

    app = FastAPI(
        title="Echo API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
    )
    app.state.settings = settings
    app.state.db = db
    app.state.gateway = gw

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_origin_regex=settings.allowed_origin_regex,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Simulate-Failure"],
        max_age=600,
    )

    @app.exception_handler(Exception)
    async def unhandled_error(_: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled error: %s", type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": "internal server error"})

    @app.get("/health")
    def health():
        try:
            db.ping()
        except Exception:
            return JSONResponse(status_code=503, content={"detail": "database unavailable"})
        if not gw.slots:
            return JSONResponse(status_code=503, content={"detail": "no API keys configured"})
        return {
            "status": "ok",
            "keys_configured": len(gw.slots),
            "cache_enabled": gw.cache_enabled,
            "model": settings.model,
            "failure_simulation_enabled": settings.enable_failure_simulation,
        }

    @app.post("/chat", response_model=ChatResponse)
    async def chat(
        body: ChatRequest,
        x_simulate_failure: Optional[str] = Header(default=None),
    ):
        started = time.perf_counter()
        user_created_at = utc_now_iso()

        stored_prompt, history = await run_in_threadpool(
            db.load_context, body.session_id, settings.max_history_messages
        )
        system_prompt = body.system_prompt or stored_prompt or settings.default_system_prompt
        messages = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": body.message},
        ]

        simulated = (
            parse_simulation_header(x_simulate_failure, gw.key_ids)
            if settings.enable_failure_simulation
            else {}
        )

        try:
            result = await gw.complete(messages, simulated)
        except AllProvidersUnavailable:
            logger.warning(
                "chat session=%s… all providers unavailable (simulated=%s)",
                body.session_id[:8],
                bool(simulated),
            )
            return JSONResponse(status_code=503, content={"detail": "all providers unavailable"})

        metadata = {
            "resolution_source": result.resolution_source,
            "model": result.model,
            "latency_ms": int(round((time.perf_counter() - started) * 1000)),
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "key_id": result.key_id,
            "fallback_attempts": result.fallback_attempts,
        }

        await run_in_threadpool(
            db.save_turn,
            body.session_id,
            body.message,
            result.reply,
            metadata,
            body.system_prompt,
            user_created_at,
        )

        logger.info(
            "chat session=%s… source=%s model=%s key=%s attempts=%d latency=%dms tokens=%d/%d",
            body.session_id[:8],
            result.resolution_source,
            result.model,
            result.key_id,
            result.fallback_attempts,
            metadata["latency_ms"],
            result.input_tokens,
            result.output_tokens,
        )
        return {"session_id": body.session_id, "reply": result.reply, "metadata": metadata}

    @app.get("/sessions/{session_id}/messages")
    async def session_messages(session_id: str):
        messages = await run_in_threadpool(db.list_messages, session_id)
        if messages is None:
            return JSONResponse(status_code=404, content={"detail": "session not found"})
        return {"session_id": session_id, "messages": messages}

    return app


app = create_app()
