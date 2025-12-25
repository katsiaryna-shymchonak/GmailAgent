# server/tools/deadline_tool.py
import logging
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
                    "reason": "",
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
        """
        Extract explicit deadlines from emails. Each deadline entry MUST include:
          - email_id: the original message 'id' field from the input messages
          - deadline: extracted date/time string
          - reason: short explanation or the sentence that contains the deadline

        If no deadlines are found, return "deadlines": [].
        """
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
    {{"email_id": "string", "deadline": "string", "reason": "string"}}
  ]
}}

Emails (each message is an object and MUST include an 'id' field):
{messages}
"""

        result = await self.call(
            prompt,
            variables={"query": user_query, "messages": messages},
            user_language=user_language,
        )

        # Defensive normalization
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
                    reason = item.get("reason") or item.get("context") or ""
                    # If email_id is missing, try to match by content heuristics (not ideal)
                    if not email_id:
                        # skip entries without explicit email_id to avoid fabricated links
                        logger.debug("DeadlineTool skipping entry without email_id: %r", item)
                        continue
                    if deadline:
                        normalized.append(
                            {
                                "email_id": str(email_id),
                                "deadline": str(deadline),
                                "reason": str(reason),
                            }
                        )
                else:
                    logger.debug("DeadlineTool unexpected item type at index %d: %r", idx, item)
        else:
            logger.debug("DeadlineTool unexpected deadlines shape: %r", raw_deadlines)

        result["deadlines"] = normalized
        return result
