# server/models/schemas.py
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class EmailMessage(BaseModel):
    id: str
    subject: Optional[str] = None
    snippet: Optional[str] = None
    from_: Optional[str] = Field(None, alias="from")
    body: Optional[str] = None

    class Config:
        populate_by_name = True


class IngestRequest(BaseModel):
    items: List[EmailMessage]


class AnalyzeRequest(BaseModel):
    session_id: Optional[str] = None
    sender_email: Optional[str] = None
    query: Optional[str] = None
    messages: List[EmailMessage] = []


class FilteredEmail(BaseModel):
    id: str
    subject: Optional[str] = None
    body: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    priority: str
    recommended_action: str

class AutoReplyTemplate(BaseModel):
    id: int
    template: str


class NewsletterInsights(BaseModel):
    unsubscribe: List[str] = Field(default_factory=list)
    keep: List[str] = Field(default_factory=list)
    digest: Optional[str] = None
    weekly_report: Optional[str] = None


class TaskItem(BaseModel):

    email_id: str
    task: str

class DeadlineItem(BaseModel):
    email_id: str
    deadline: str
    description: str


# ---------------------------
# KEY POINTS
# ---------------------------
class KeyPointItem(BaseModel):
    email_id: str
    points: List[str]

class AnalyzeResponse(BaseModel):
    summary: str

    key_tasks: List[TaskItem] = Field(default_factory=list)
    deadlines: List[DeadlineItem] = Field(default_factory=list)

    filter_results: List[FilteredEmail] = Field(default_factory=list)
    newsletter_insights: NewsletterInsights = Field(default_factory=NewsletterInsights)
    auto_replies: List[AutoReplyTemplate] = Field(default_factory=list)

    messages: List[dict] = Field(default_factory=list)
    capabilities_tip: Optional[str] = None
    raw_model_output: Optional[str] = None

    key_points: List[KeyPointItem] = Field(default_factory=list)
