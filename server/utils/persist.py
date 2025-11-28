"""Persistence utilities for AgentOrchestrator"""
from typing import Any, Dict, List
from server.services.database import store_email_memory


def persist_memory(messages: List[Dict[str, Any]], filter_result: Dict[str, Any]) -> None:
    """
    Persist email analysis results to database.

    Args:
        messages: Original email messages (dicts)
        filter_result: Filter tool results with categorization
    """
    # Словарь исходных писем по id
    email_map = {
        msg.get("id"): msg
        for msg in messages
        if isinstance(msg, dict) and msg.get("id")
    }

    records: List[Dict[str, Any]] = []
    for item in filter_result.get("emails", []):
        # Пропускаем строки и другие неподходящие типы
        if not isinstance(item, dict):
            continue

        msg = email_map.get(item.get("id"))
        if not msg:
            continue

        records.append({
            "id": item.get("id"),
            "sender_email": msg.get("from") or msg.get("from_"),
            "subject": msg.get("subject"),
            "snippet": msg.get("snippet"),
            "body": msg.get("body"),
            "email_type": item.get("type"),
            "priority": item.get("priority"),
            "requires_reply": item.get("requires_reply"),
            "tags": item.get("tags"),
            "metadata": item,
        })

    if records:
        store_email_memory(records)
