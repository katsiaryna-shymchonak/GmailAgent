# server/api/routes.py
import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from ..config.settings import get_settings, Settings
from ..core.orchestrator import AgentOrchestrator
from ..services.database import init_memory_table, init_active_emails_table
from ..metrics.llm_counters import log_snapshot

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Pydantic models for requests/responses (self-contained) ---
class AnalyzeRequest(BaseModel):
    session_id: Optional[str] = None
    sender_email: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None
    query: Optional[str] = None


class MessageItem(BaseModel):
    role: str
    tool: Optional[str] = None
    content: str


class AnalyzeResponse(BaseModel):
    summary: Optional[str] = ""
    filter_results: Optional[List[Dict[str, Any]]] = []
    newsletter_insights: Optional[Dict[str, Any]] = {}
    auto_replies: Optional[List[Dict[str, Any]]] = []
    messages: Optional[List[MessageItem]] = []
    capabilities_tip: Optional[str] = ""
    key_tasks: Optional[List[Dict[str, Any]]] = []
    deadlines: Optional[List[Dict[str, Any]]] = []
    key_points: Optional[List[Dict[str, Any]]] = []


# --- Dependency to get settings ---
def get_cfg() -> Settings:
    return get_settings()


# --- Health endpoint (simple) ---
@router.get("/health", tags=["system"])
async def health() -> Dict[str, Any]:
    return {"status": "ok"}


# --- Initial analysis endpoint ---
@router.post("/analyze/initial", response_model=AnalyzeResponse, tags=["agent"])
async def analyze_initial(payload: AnalyzeRequest, cfg: Settings = Depends(get_cfg)) -> AnalyzeResponse:
    """
    Expected payload:
    {
      "session_id": "user@example.com" | "default",   # optional, used as session key
      "sender_email": "...",                           # legacy name supported
      "messages": [ ... ],                             # list of selected emails
      "query": "optional custom query"                 # optional
    }
    This endpoint saves active emails (session) and runs initial summary pipeline.
    """
    agent = AgentOrchestrator()
    session_id = payload.session_id or payload.sender_email or "default"
    messages = payload.messages or []
    query = payload.query

    try:
        # initial_summary should save active emails and return structured response
        if query:
            result = await agent.initial_summary(messages=messages, query=query, sender_email=session_id)
        else:
            result = await agent.initial_summary(messages=messages, sender_email=session_id)

        if isinstance(result, AnalyzeResponse):
            return result
        if isinstance(result, dict):
            return AnalyzeResponse(**result)
        # fallback: wrap into AnalyzeResponse
        return AnalyzeResponse(summary="Agent returned unexpected result", messages=[])
    except Exception as e:
        logger.exception("Initial analysis failed: %s", e)
        return AnalyzeResponse(summary="Initial analysis failed", messages=[])


# --- Follow-up endpoint (uses active emails stored by session_id) ---
@router.post("/analyze/followup", response_model=AnalyzeResponse, tags=["agent"])
async def analyze_followup(payload: AnalyzeRequest, cfg: Settings = Depends(get_cfg)) -> AnalyzeResponse:
    """
    Expected payload:
    {
      "session_id": "user@example.com" | "default",  # optional, used as session key
      "sender_email": "...",                          # legacy name supported
      "query": "What are the key points?"
    }
    Note: messages are NOT required here; orchestrator will load active emails from DB.
    """
    agent = AgentOrchestrator()
    session_id = payload.session_id or payload.sender_email or "default"
    query = payload.query or ""

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


# --- Generic analyze endpoint (full payload) ---
@router.post("/analyze/emails", response_model=AnalyzeResponse, tags=["agent"])
async def analyze_emails(payload: AnalyzeRequest, cfg: Settings = Depends(get_cfg)) -> AnalyzeResponse:
    """
    Backwards-compatible endpoint that accepts messages + query + sender_email.
    """
    agent = AgentOrchestrator()
    session_id = payload.session_id or payload.sender_email or "default"
    messages = payload.messages or []
    query = payload.query or None

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


# --- Weekly report endpoint (optional) ---
@router.post("/analyze/weekly", response_model=AnalyzeResponse, tags=["agent"])
async def analyze_weekly(payload: AnalyzeRequest, cfg: Settings = Depends(get_cfg)) -> AnalyzeResponse:
    agent = AgentOrchestrator()
    session_id = payload.session_id or payload.sender_email or "default"
    messages = payload.messages or []
    query = payload.query or "Create weekly report"

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


# --- Router registration helper to create FastAPI app with startup tasks ---
def create_app(settings: Optional[Settings] = None) -> FastAPI:
    cfg = settings or get_settings()
    app = FastAPI(title=cfg.app_name, debug=cfg.debug)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # include router
    app.include_router(router)

    # startup: ensure DB tables exist and start periodic metrics logging
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

        # periodic snapshot logger (non-blocking)
        async def _periodic_metrics():
            while True:
                try:
                    log_snapshot()
                except Exception:
                    logger.exception("Periodic metrics snapshot failed")
                await asyncio.sleep(60)

        # spawn background task
        try:
            import asyncio as _asyncio
            _asyncio.create_task(_periodic_metrics())
        except Exception:
            logger.exception("Failed to start periodic metrics task")

    return app
