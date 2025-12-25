# server/tools/content_analysis.py
import logging
from typing import Dict, Any, List
from .base import BaseTool

logger = logging.getLogger(__name__)


class ContentAnalysisTool(BaseTool):
    name = "content"

    def __init__(self):
        # Только summary — никаких других полей
        schema = {
            "summary": ""
        }
        super().__init__(schema=schema, tool_name=self.name)

    async def run(
        self,
        messages: List[Dict[str, Any]],
        user_query: str = "Summarize these emails.",
        user_language: str = "English"
    ) -> Dict[str, Any]:

        prompt = f"""
        You are a summarization tool.

        LANGUAGE REQUIREMENT:
        - Respond strictly in {user_language}.

        YOUR ONLY TASK:
        - Produce a clean summary of the provided emails.

        Output strictly valid JSON:
        {{
          "summary": "string"
        }}

        Emails:
        {messages}
        """

        result = await self.call(
            prompt,
            variables={"messages": messages, "query": user_query},
            user_language=user_language
        )

        # Defensive normalization
        if not isinstance(result, dict):
            return {"summary": ""}

        summary = result.get("summary", "")
        if not isinstance(summary, str):
            summary = str(summary)

        return {"summary": summary}
