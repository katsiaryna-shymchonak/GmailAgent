from __future__ import annotations

import logging
from typing import Any

import google.generativeai as genai
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agent import AgentOrchestrator
from .config import Settings, get_settings
from .database import init_memory_table
from .schemas import AnalyzeRequest, AnalyzeResponse, WeeklySummaryRequest

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
    def health() -> dict[str, Any]:
        return {"status": "ok"}

    @app.on_event("startup")
    def _startup() -> None:
        init_memory_table()

    agent = AgentOrchestrator()

    @app.post("/analyze/emails", response_model=AnalyzeResponse, tags=["agent"])
    def analyze(payload: AnalyzeRequest, cfg: Settings = Depends(get_settings)) -> AnalyzeResponse:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is missing")
        genai.configure(api_key=settings.gemini_api_key)
        result = agent.analyze_emails(payload.messages, payload.query, payload.sender_email)
        return AnalyzeResponse(**result)

    @app.post("/analyze/weekly", response_model=AnalyzeResponse, tags=["agent"])
    def analyze_weekly(payload: WeeklySummaryRequest | None = None, cfg: Settings = Depends(get_settings)) -> AnalyzeResponse:
        if not payload:
            payload = WeeklySummaryRequest()
        query = payload.query or "Сформируй недельный отчёт"
        messages = payload.messages or []
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is missing")
        genai.configure(api_key=settings.gemini_api_key)
        result = agent.weekly_summary(query, messages)
        return AnalyzeResponse(**result)

    return app


app = create_app()
