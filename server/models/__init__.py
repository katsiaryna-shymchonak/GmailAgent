"""Data models and schemas"""
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    EmailMessage,
    IngestRequest,
    WeeklySummaryRequest,
)

__all__ = [
    "EmailMessage",
    "IngestRequest",
    "AnalyzeRequest",
    "AnalyzeResponse",
    "WeeklySummaryRequest",
]

