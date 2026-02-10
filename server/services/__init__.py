"""Services module"""
from .database import (
    fetch_recent_emails,
    get_connection,
    get_pool,
    get_weekly_metrics,
    init_memory_table
)
from .embeddings import embed_texts

__all__ = [
    "get_pool",
    "get_connection",
    "init_memory_table",
    "get_weekly_metrics",
    "fetch_recent_emails",
    "embed_texts",
]

