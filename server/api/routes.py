import logging
import json
from typing import Any

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..config.settings import Settings, get_settings
from ..core.orchestrator import AgentOrchestrator
from ..models import AnalyzeRequest, AnalyzeResponse
from ..services.database import init_memory_table

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, Any]:
        return {"status": "ok"}

    @app.on_event("startup")
    async def _startup() -> None:
        init_memory_table()

    agent = AgentOrchestrator()

    # --- основной старый эндпоинт ---
    @app.post("/analyze/emails", response_model=AnalyzeResponse, tags=["agent"])
    async def analyze(
        payload: AnalyzeRequest, cfg: Settings = Depends(get_settings)
    ) -> AnalyzeResponse:
        try:
            result = await agent.analyze_emails(
                messages=payload.messages,
                query=payload.query,
                sender_email=payload.sender_email,
            )
            if isinstance(result, BaseModel):
                result = result.dict()
            if not isinstance(result, dict):
                logger.error("Agent returned non-dict result: %s", type(result))
                return AnalyzeResponse(summary="Agent error", messages=[])

            return AnalyzeResponse(**result)
        except Exception as e:
            logger.exception("Analysis failed: %s", e)
            return AnalyzeResponse(
                summary="Analysis failed",
                messages=[{"role": "agent", "tool": "system", "content": "Sorry, analysis failed."}],
            )

    # --- новый эндпоинт: только summary ---
    @app.post("/analyze/initial", response_model=AnalyzeResponse, tags=["agent"])
    async def analyze_initial(payload: dict[str, Any]) -> AnalyzeResponse:
        try:
            result = await agent.initial_summary(
                messages=payload.get("messages", []),
                sender_email=payload.get("sender_email"),
            )
            if isinstance(result, BaseModel):
                result = result.dict()


            return AnalyzeResponse(**result)
        except Exception as e:
            logger.exception("Initial analysis failed: %s", e)
            return AnalyzeResponse(summary="Initial analysis failed", messages=[])

    # --- новый эндпоинт: follow-up ---
    @app.post("/analyze/followup", response_model=AnalyzeResponse, tags=["agent"])
    async def analyze_followup(payload: dict[str, Any]) -> AnalyzeResponse:
        try:
            result = await agent.follow_up(
                messages=payload.get("messages", []),
                query=payload.get("query", ""),
                sender_email=payload.get("sender_email"),
            )
            if isinstance(result, BaseModel):
                result = result.dict()


            return AnalyzeResponse(**result)
        except Exception as e:
            logger.exception("Follow-up analysis failed: %s", e)
            return AnalyzeResponse(summary="Follow-up analysis failed", messages=[])

    return app
