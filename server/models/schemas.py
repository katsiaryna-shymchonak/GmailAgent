"""Pydantic schemas for API requests and responses"""
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class EmailMessage(BaseModel):
    """Email message data model"""
    id: str = Field(..., description="Gmail message identifier")
    subject: Optional[str] = None
    snippet: Optional[str] = None
    from_: Optional[str] = Field(None, alias="from")
    body: Optional[str] = None

    class Config:
        populate_by_name = True


class IngestRequest(BaseModel):
    """Request model for ingesting emails"""
    items: List[EmailMessage]


class AnalyzeRequest(BaseModel):
    """Request model for email analysis"""
    query: str = Field(default="Summarize these emails")
    sender_email: Optional[str] = None
    messages: List[EmailMessage]


class AnalyzeResponse(BaseModel):
    """Response model for email analysis"""
    summary: str
    key_tasks: List[str] = Field(default_factory=list)
    deadlines: List[str] = Field(default_factory=list)
    draft_reply: str = ""
    filter_results: List[dict] = Field(default_factory=list)
    newsletter_insights: dict = Field(default_factory=dict)
    auto_replies: List[dict] = Field(default_factory=list)
    weekly_report: str = ""
    messages: List[dict] = Field(default_factory=list)
    capabilities_tip: Optional[str] = None
    raw_model_output: str | None = None


class WeeklySummaryRequest(BaseModel):
    """Request model for weekly summary generation"""
    query: str = Field(default="Сформируй недельный отчёт по почте")
    messages: List[EmailMessage] = Field(default_factory=list)

