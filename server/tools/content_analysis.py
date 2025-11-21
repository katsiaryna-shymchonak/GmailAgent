"""Content analysis tool for extracting key information"""
import textwrap
from typing import Any, Dict, List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI

from .base import BaseTool
from .utils import format_messages


class ContentAnalysisTool(BaseTool):
    """Tool for analyzing email content and extracting tasks/deadlines using LangChain"""
    name = "Анализ содержания писем"

    def __init__(self, llm: Optional[ChatGoogleGenerativeAI] = None) -> None:
        """Initialize content analysis tool with LangChain LLM"""
        super().__init__(llm)

    def run(self, *, messages: List[Dict[str, Any]], user_query: str) -> Dict[str, Any]:
        """
        Extract key information, tasks, deadlines, and generate summary from emails

        Args:
            messages: List of email message dictionaries
            user_query: User's query or instruction

        Returns:
            Dictionary with summary, key tasks, deadlines, and draft reply
        """
        prompt = textwrap.dedent(
            f"""
            Ты анализируешь письма.
            Извлеки ключевые задачи/дедлайны, сделай summary и draft-ответ (пример: «Спасибо, отчёт будет готов к четвергу»).
            Формат JSON:
            {{
              "summary": "...",
              "key_tasks": ["..."],
              "deadlines": ["..."],
              "draft_reply": "...",
              "raw": "опционально"
            }}

            Запрос пользователя: {user_query or "Сформируй резюме писем."}

            Письма:
            {format_messages(messages)}
            """
        ).strip()
        return self._call_model(prompt)

