import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from ..config.settings import get_settings, Settings
from ..core.orchestrator import AgentOrchestrator
from ..services.database import init_memory_table, init_active_emails_table
from ..metrics.llm_counters import log_snapshot

from ..models.schemas import AnalyzeResponse, AnalyzeRequest

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Dependency to get settings ---
def get_cfg() -> Settings:
    return get_settings()


# --- Health endpoint ---
@router.get("/health", tags=["system"])
async def health() -> Dict[str, Any]:
    return {"status": "ok"}


# --- Initial analysis endpoint ---
@router.post("/analyze/initial", response_model=AnalyzeResponse, tags=["agent"])
async def analyze_initial(payload: AnalyzeRequest, cfg: Settings = Depends(get_cfg)) -> AnalyzeResponse:
    agent = AgentOrchestrator()
    session_id = payload.session_id or payload.sender_email or "default"
    messages = payload.messages or []
    query = payload.query

    logger.info(
        "INITIAL REQUEST: session_id=%r sender_email=%r query=%r messages_count=%d",
        session_id,
        payload.sender_email,
        query,
        len(messages),
    )

    try:
        if query:
            result = await agent.initial_summary(messages=messages, query=query, sender_email=session_id)
        else:
            result = await agent.initial_summary(messages=messages, sender_email=session_id)

        if isinstance(result, AnalyzeResponse):
            return result
        if isinstance(result, dict):
            return AnalyzeResponse(**result)

        return AnalyzeResponse(summary="Agent returned unexpected result", messages=[])
    except Exception as e:
        logger.exception("Initial analysis failed: %s", e)
        return AnalyzeResponse(summary="Initial analysis failed", messages=[])


# --- Follow-up endpoint ---
@router.post("/analyze/followup", response_model=AnalyzeResponse, tags=["agent"])
async def analyze_followup(payload: AnalyzeRequest, cfg: Settings = Depends(get_cfg)) -> AnalyzeResponse:
    agent = AgentOrchestrator()
    session_id = payload.session_id or payload.sender_email or "default"
    query = payload.query or ""

    logger.info(
        "FOLLOW-UP REQUEST: session_id=%r sender_email=%r query=%r",
        session_id,
        payload.sender_email,
        query,
    )

    try:
        result = await agent.follow_up(messages=[], query=query, sender_email=session_id)

        if isinstance(result, AnalyzeResponse):
            return result
        if isinstance(result, dict):
            return AnalyzeResponse(**result)

        return AnalyzeResponse(summary="Agent returned unexpected result", messages=[])
    except Exception as e:
        logger.exception("Follow-up analysis failed: %s", e)
        return AnalyzeResponse(summary="Follow-up analysis failed", messages=[])


# --- Generic analyze endpoint ---
@router.post("/analyze/emails", response_model=AnalyzeResponse, tags=["agent"])
async def analyze_emails(payload: AnalyzeRequest, cfg: Settings = Depends(get_cfg)) -> AnalyzeResponse:
    agent = AgentOrchestrator()
    session_id = payload.session_id or payload.sender_email or "default"
    messages = payload.messages or []
    query = payload.query or None

    logger.info(
        "ANALYZE EMAILS REQUEST: session_id=%r sender_email=%r query=%r messages_count=%d",
        session_id,
        payload.sender_email,
        query,
        len(messages),
    )

    try:
        result = await agent.analyze_emails(messages=messages, query=query, sender_email=session_id)

        if isinstance(result, AnalyzeResponse):
            return result
        if isinstance(result, dict):
            return AnalyzeResponse(**result)

        return AnalyzeResponse(summary="Agent returned unexpected result", messages=[])
    except Exception as e:
        logger.exception("Analyze emails failed: %s", e)
        return AnalyzeResponse(summary="Analyze failed", messages=[])


# --- Weekly report endpoint ---
@router.post("/analyze/weekly", response_model=AnalyzeResponse, tags=["agent"])
async def analyze_weekly(payload: AnalyzeRequest, cfg: Settings = Depends(get_cfg)) -> AnalyzeResponse:
    agent = AgentOrchestrator()
    session_id = payload.session_id or payload.sender_email or "default"
    messages = payload.messages or []
    query = payload.query or "Create weekly report"

    logger.info(
        "WEEKLY REQUEST: session_id=%r sender_email=%r query=%r messages_count=%d",
        session_id,
        payload.sender_email,
        query,
        len(messages),
    )

    try:
        result = await agent.weekly_report(messages=messages, query=query, sender_email=session_id)

        if isinstance(result, AnalyzeResponse):
            return result
        if isinstance(result, dict):
            return AnalyzeResponse(**result)

        return AnalyzeResponse(summary="Agent returned unexpected result", messages=[])
    except Exception as e:
        logger.exception("Weekly analysis failed: %s", e)
        return AnalyzeResponse(summary="Weekly analysis failed", messages=[])


# --- Prometheus metrics endpoint ---
@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


# --- Router registration helper ---
def create_app(settings: Optional[Settings] = None) -> FastAPI:
    cfg = settings or get_settings()
    app = FastAPI(title=cfg.app_name, debug=cfg.debug)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.on_event("startup")
    async def _startup() -> None:
        try:
            init_memory_table()
        except Exception:
            logger.exception("Failed to initialize memory table")

        try:
            init_active_emails_table()
        except Exception:
            logger.exception("Failed to initialize active_emails table")

        async def _periodic_metrics():
            while True:
                try:
                    log_snapshot()
                except Exception:
                    logger.exception("Periodic metrics snapshot failed")
                await asyncio.sleep(60)

        try:
            import asyncio as _asyncio
            _asyncio.create_task(_periodic_metrics())
        except Exception:
            logger.exception("Failed to start periodic metrics task")

    return app
