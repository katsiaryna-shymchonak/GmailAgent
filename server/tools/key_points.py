import logging
from typing import Dict, Any, List
from .base import BaseTool

logger = logging.getLogger(__name__)


class KeyPointsTool(BaseTool):
    name = "key_points"

    def __init__(self):
        # Расширенная схема для поддержки ключевых задач
        schema = {
            "summary": "",
            "key_points": [
                {
                    "email_id": "",
                    "points": [""],
                }
            ],
            "key_tasks": [
                {
                    "email_id": "",
                    "task": "",
                }
            ],
        }
        super().__init__(schema=schema, tool_name=self.name)

    async def run(
            self,
            messages: List[Dict[str, Any]],
            user_query: str = "Extract key points and tasks from each email.",
            user_language: str = "English",
    ) -> Dict[str, Any]:
        """
        Извлекает ключевые тезисы и конкретные задачи (actions) из каждого письма.
        """
        prompt = f"""
You are a tool that extracts key points and key tasks (action items) from emails.

LANGUAGE REQUIREMENT:
- Respond strictly in {user_language}.

YOUR TASKS:
1. Extract key bullet points summarizing the main information.
2. Identify specific tasks, requests, or action items that the user needs to perform.

IMPORTANT:
- Focus only on content. Do not perform filtering or classification.
- Output strictly valid JSON matching the schema below.

Output schema:
{{
  "summary": "string",
  "key_points": [
    {{"email_id": "string", "points": ["string"]}}
  ],
  "key_tasks": [
    {{"email_id": "string", "task": "string"}}
  ]
}}

Emails:
{messages}
"""

        result = await self.call(
            prompt,
            variables={"query": user_query, "messages": messages},
            user_language=user_language,
        )

        if not isinstance(result, dict):
            result = {}

        # Нормализация key_points
        raw_kp = result.get("key_points", [])
        normalized_kp = []
        if isinstance(raw_kp, list):
            for idx, item in enumerate(raw_kp):
                if isinstance(item, dict):
                    eid = str(item.get("email_id") or item.get("id") or f"email_{idx}")
                    pts = item.get("points", [])
                    if isinstance(pts, list):
                        pts = [str(p).strip() for p in pts if p]
                        if pts:
                            normalized_kp.append({"email_id": eid, "points": pts})

        # Нормализация key_tasks (новое поле)
        raw_kt = result.get("key_tasks", [])
        normalized_kt = []
        if isinstance(raw_kt, list):
            for idx, item in enumerate(raw_kt):
                if isinstance(item, dict):
                    eid = str(item.get("email_id") or item.get("id") or f"task_{idx}")
                    task = item.get("task") or ""
                    if task:
                        normalized_kt.append({"email_id": eid, "task": str(task)})

        result["key_points"] = normalized_kp
        result["key_tasks"] = normalized_kt
        return result