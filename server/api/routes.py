"""API routes and endpoints"""
import logging
from typing import Any

import google.generativeai as genai
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import Settings, get_settings
from ..core import AgentOrchestrator
from ..models import AnalyzeRequest, AnalyzeResponse, WeeklySummaryRequest
from ..services.database import init_memory_table

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Create and configure FastAPI application
    
    Args:
        settings: Optional settings instance (uses default if not provided)
        
    Returns:
        Configured FastAPI application instance
    """
    settings = settings or get_settings()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"])
    def health() -> dict[str, Any]:
        """Health check endpoint"""
        return {"status": "ok"}

    @app.on_event("startup")
    def _startup() -> None:
        """Initialize database on startup"""
        init_memory_table()

    # Initialize agent orchestrator
    agent = AgentOrchestrator()

    @app.post("/analyze/emails", response_model=AnalyzeResponse, tags=["agent"])
    def analyze(
        payload: AnalyzeRequest, cfg: Settings = Depends(get_settings)
    ) -> AnalyzeResponse:
        """
        Analyze selected emails using AI agent
        
        Args:
            payload: Analysis request with emails and query
            cfg: Application settings
            
        Returns:
            Analysis results with insights and recommendations
        """
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is missing")
        genai.configure(api_key=settings.gemini_api_key)
        result = agent.analyze_emails(payload.messages, payload.query, payload.sender_email)
        return AnalyzeResponse(**result)

    @app.post("/analyze/weekly", response_model=AnalyzeResponse, tags=["agent"])
    def analyze_weekly(
        payload: WeeklySummaryRequest | None = None, cfg: Settings = Depends(get_settings)
    ) -> AnalyzeResponse:
        """
        Generate weekly summary report
        
        Args:
            payload: Weekly summary request (optional)
            cfg: Application settings
            
        Returns:
            Weekly summary report with insights
        """
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

