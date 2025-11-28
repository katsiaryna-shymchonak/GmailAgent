"""Data models and schemas"""
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    EmailMessage,
    IngestRequest,
)

__all__ = [
    "EmailMessage",
    "IngestRequest",
    "AnalyzeRequest",
    "AnalyzeResponse",
]

