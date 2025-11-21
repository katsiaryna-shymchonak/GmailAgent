"""Newsletter management tool"""
import json
import textwrap
from typing import Any, Dict, List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI

from .base import BaseTool


class NewsletterTool(BaseTool):
    """Tool for managing newsletters and subscriptions using LangChain"""
    name = "Умное управление рассылками"

    def __init__(self, llm: Optional[ChatGoogleGenerativeAI] = None) -> None:
        """Initialize newsletter tool with LangChain LLM"""
        super().__init__(llm)

    def run(
        self,
        *,
        messages: List[Dict[str, Any]],
        filter_data: Dict[str, Any],
        weekly_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze newsletters and provide unsubscribe recommendations

        Args:
            messages: List of email messages
            filter_data: Filtered email categorization data
            weekly_metrics: Weekly email statistics

        Returns:
            Dictionary with unsubscribe suggestions, keep recommendations, digest, and weekly report
        """
        prompt = textwrap.dedent(
            f"""
            Ты помогаешь управлять рассылками.
            На основе данных о письмах и еженедельных метрик предложи:
              - от каких рассылок отписаться,
              - какие оставить,
              - сформируй digest (краткий обзор),
              - сделай недельный отчёт по статистике (кол-во писем, митингов, рассылок, % requiring reply vs информационных).

            Обязательно JSON:
            {{
              "unsubscribe": ["..."],
              "keep": ["..."],
              "digest": "...",
              "weekly_report": "...",
              "metrics_used": {{...}}
            }}

            Классификация писем: {json.dumps(filter_data.get('emails', []), ensure_ascii=False)}

            Метрики за неделю: {json.dumps(weekly_metrics, default=str, ensure_ascii=False)}
            """
        ).strip()
        return self._call_model(prompt, temperature=0.1)

