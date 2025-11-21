"""Auto-reply template generation tool"""
import json
import textwrap
from typing import Any, Dict, List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI

from .base import BaseTool


class AutoReplyTool(BaseTool):
    """Tool for generating personalized auto-reply templates using LangChain"""
    name = "Персонализированные автоответы"

    def __init__(self, llm: Optional[ChatGoogleGenerativeAI] = None) -> None:
        """Initialize auto-reply tool with LangChain LLM"""
        super().__init__(llm)

    def run(self, *, messages: List[Dict[str, Any]], filter_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate personalized auto-reply templates for common email types

        Args:
            messages: List of email message dictionaries
            filter_data: Filtered email categorization data

        Returns:
            Dictionary with reply templates and general templates
        """
        prompt = textwrap.dedent(
            f"""
            Создай персонализированные шаблоны автоответов для типовых писем.
            Используй примеры:
              - «Спасибо за информацию»
              - «Принято, добавлю в план»
              - «Неактуально для меня, но спасибо»

            Верни JSON:
            {{
              "templates": [
                {{
                  "id": "...",
                  "subject": "...",
                  "type": "meeting/newsletter/...",
                  "template": "...",
                  "notes": "когда использовать"
                }}
              ],
              "general_templates": ["...", ...]
            }}

            Классификация писем: {json.dumps(filter_data.get('emails', []), ensure_ascii=False)}
            """
        ).strip()
        return self._call_model(prompt, temperature=0.3)

