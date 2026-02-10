# server/tools/deadline_tool.py
import logging
import json
from typing import Dict, Any, List
from .base import BaseTool

logger = logging.getLogger(__name__)


class DeadlineTool(BaseTool):
    name = "deadlines"

    def __init__(self):
        schema = {
            "summary": "",
            "deadlines": [
                {
                    "email_id": "",
                    "deadline": "",
                    "description": "",
                }
            ],
        }
        super().__init__(schema=schema, tool_name=self.name)

    async def run(
        self,
        messages: List[Dict[str, Any]],
        user_query: str = "Extract explicit deadlines from emails and attach email_id.",
        user_language: str = "English",
    ) -> Dict[str, Any]:

        # FIX: convert messages to proper JSON
        emails_json = json.dumps(messages, ensure_ascii=False)

        prompt = f"""
You are a strict extractor of deadlines from email content.

LANGUAGE REQUIREMENT:
- Respond strictly in {user_language}.

REQUIREMENTS:
- You MUST output ONLY valid JSON and ONLY the fields in the schema below.
- For every deadline you extract, you MUST include the original email's 'id' as "email_id".
- DO NOT invent or fabricate email IDs. Use the 'id' field from the provided messages.
- If a message contains multiple explicit deadlines, include each as a separate object referencing the same email_id.
- If no deadlines are present, return an empty list for "deadlines".

Output schema:
{{
  "summary": "string",
  "deadlines": [
    {{"email_id": "string", "deadline": "string", "description": "string"}}
  ]
}}

Emails (JSON array, each object MUST include an 'id'):
{emails_json}
"""

        logger.info("DeadlineTool prompt prepared (len=%d)", len(prompt))

        result = await self.call(
            prompt,
            variables={"query": user_query, "messages": messages},
            user_language=user_language,
        )

        logger.info("Raw LLM result (DeadlineTool): %s", result)

        if not isinstance(result, dict):
            result = {}

        result.setdefault("summary", "")

        raw_deadlines = result.get("deadlines", [])
        normalized: List[Dict[str, Any]] = []

        if isinstance(raw_deadlines, list):
            for idx, item in enumerate(raw_deadlines):
                if isinstance(item, dict):
                    email_id = item.get("email_id") or item.get("id")
                    deadline = item.get("deadline") or ""
                    description = item.get("description") or item.get("context") or ""

                    if not email_id:
                        logger.info("DeadlineTool skipping entry without email_id: %r", item)
                        continue

                    if deadline:
                        normalized.append(
                            {
                                "email_id": str(email_id),
                                "deadline": str(deadline),
                                "description": str(description),
                            }
                        )
                    else:
                        logger.info("DeadlineTool skipping entry without deadline: %r", item)
                else:
                    logger.info("DeadlineTool unexpected item type at index %d: %r", idx, item)
        else:
            logger.info("DeadlineTool unexpected deadlines shape: %r", raw_deadlines)

        result["deadlines"] = normalized

        # Ensure summary is string
        if not isinstance(result.get("summary"), str):
            result["summary"] = ""

        logger.info("Final result (DeadlineTool): %s", result)
        return result
