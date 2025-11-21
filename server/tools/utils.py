"""Utility functions for tools"""
import textwrap
from typing import Any, Dict, Iterable


def format_messages(messages: Iterable[Dict[str, Any]]) -> str:
    """
    Format email messages into a readable string for prompts

    Args:
        messages: Iterable of email message dictionaries

    Returns:
        Formatted string with all email details
    """
    sections = []
    for idx, message in enumerate(messages, start=1):
        sections.append(
            textwrap.dedent(
                f"""
                Email {idx}:
                ID: {message.get('id')}
                From: {message.get('from') or message.get('from_') or message.get('sender_email')}
                Subject: {message.get('subject')}
                Snippet: {message.get('snippet')}
                Body:
                {message.get('body') or message.get('content') or message.get('snippet')}
                """
            ).strip()
        )
    return "\n\n".join(sections) if sections else "Нет содержимого."

