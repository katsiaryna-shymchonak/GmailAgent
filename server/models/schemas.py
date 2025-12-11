from typing import Dict, List, Optional, Any
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


# --- Filtering tool extended contract ---
class FilteredEmail(BaseModel):
    """Result of filtering and prioritization for a single email"""
    id: str
    subject: Optional[str] = None
    body: Optional[str] = None
    tags: List[str] = Field(
        default_factory=list,
        description="Relevant tags such as 'meeting', 'urgent', 'newsletter'"
    )
    priority: str = Field(..., description="Priority level: high, medium, low")
    recommended_action: str = Field(..., description="Recommended action: reply, archive, follow-up, ignore")


# --- Auto-reply tool contract ---
class AutoReplyTemplate(BaseModel):
    """Auto-reply template"""
    id: int
    template: str


# --- Newsletter tool contract ---
class NewsletterInsights(BaseModel):
    """Insights from newsletter analysis"""
    unsubscribe: List[str] = Field(default_factory=list)
    keep: List[str] = Field(default_factory=list)
    digest: Optional[str] = None
    weekly_report: Optional[str] = None


# --- Task & Deadline contracts ---
class TaskItem(BaseModel):
    """Task extracted from an email"""
    email_id: str
    task: str


class DeadlineItem(BaseModel):
    """Deadline extracted from an email"""
    email_id: str
    deadline: str


class AnalyzeResponse(BaseModel):
    """Response model for email analysis"""
    summary: str
    key_tasks: List[TaskItem] = Field(default_factory=list)
    deadlines: List[DeadlineItem] = Field(default_factory=list)
    filter_results: List[FilteredEmail] = Field(default_factory=list)
    newsletter_insights: NewsletterInsights = Field(default_factory=NewsletterInsights)
    auto_replies: List[AutoReplyTemplate] = Field(default_factory=list)
    messages: List[dict] = Field(default_factory=list)
    capabilities_tip: Optional[str] = None
    raw_model_output: Optional[str] = None
    key_points: List[Dict[str, Any]] = Field(default_factory=list)



