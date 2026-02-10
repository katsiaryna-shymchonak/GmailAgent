# server/tools/key_points.py
import logging
import json
from typing import Dict, Any, List
from .base import BaseTool

logger = logging.getLogger(__name__)


class KeyPointsTool(BaseTool):
    name = "key_points"

    def __init__(self):
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

        # FIX: convert messages to proper JSON
        emails_json = json.dumps(messages, ensure_ascii=False)

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

Emails (JSON array):
{emails_json}
"""

        logger.info("KeyPointsTool prompt prepared (len=%d)", len(prompt))

        result = await self.call(
            prompt,
            variables={"query": user_query, "messages": messages},
            user_language=user_language,
        )

        logger.info("Raw LLM result (KeyPointsTool): %s", result)

        if not isinstance(result, dict):
            result = {}

        # Normalize key_points
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
                    else:
                        logger.info("KeyPointsTool: 'points' is not list for item %d: %r", idx, item)
                else:
                    logger.info("KeyPointsTool unexpected item type at index %d: %r", idx, item)
        else:
            logger.info("KeyPointsTool unexpected key_points shape: %r", raw_kp)

        logger.info("Normalized key_points: %s", normalized_kp)

        # Normalize key_tasks
        raw_kt = result.get("key_tasks", [])
        normalized_kt = []
        if isinstance(raw_kt, list):
            for idx, item in enumerate(raw_kt):
                if isinstance(item, dict):
                    eid = str(item.get("email_id") or item.get("id") or f"task_{idx}")
                    task = item.get("task") or ""
                    if task:
                        normalized_kt.append({"email_id": eid, "task": str(task)})
                else:
                    logger.info("KeyPointsTool unexpected task item type at index %d: %r", idx, item)
        else:
            logger.info("KeyPointsTool unexpected key_tasks shape: %r", raw_kt)

        logger.info("Normalized key_tasks: %s", normalized_kt)

        # Finalize
        result["key_points"] = normalized_kp
        result["key_tasks"] = normalized_kt

        # Ensure summary is string
        if not isinstance(result.get("summary"), str):
            result["summary"] = ""

        logger.info("Final result (KeyPointsTool): %s", result)
        return result
