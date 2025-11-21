"""Email filtering and prioritization tool"""
import textwrap
from typing import Any, Dict, List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI

from .base import BaseTool
from .utils import format_messages


class FilteringTool(BaseTool):
    """Tool for categorizing and prioritizing emails using LangChain"""
    name = "Фильтрация и приоритизация"

    def __init__(self, llm: Optional[ChatGoogleGenerativeAI] = None) -> None:
        """Initialize filtering tool with LangChain LLM"""
        super().__init__(llm)

    def run(self, *, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze emails and categorize them by type, priority, and required actions

        Args:
            messages: List of email message dictionaries

        Returns:
            Dictionary with categorized emails, summary, and high priority IDs
        """
        prompt = textwrap.dedent(
            f"""
            Ты помощник по почте. Для каждого письма определи тип (meeting | newsletter | personal | work),
            приоритет (high | normal | low), нужно ли отвечать, какие теги добавить (Meetings, Newsletters, Action Required),
            и какие действия выполнить (например, добавить встречу в календарь).

            Верни JSON:
            {{
              "emails": [
                {{
                  "id": "...",
                  "type": "...",
                  "priority": "...",
                  "requires_reply": true/false,
                  "tags": ["...", ...],
                  "actions": ["...", ...],
                  "notes": "краткое пояснение"
                }}
              ],
              "summary": "краткое описание",
              "high_priority_ids": ["...", ...]
            }}

            Письма:
            {format_messages(messages)}
            """
        ).strip()
        return self._call_model(prompt)

