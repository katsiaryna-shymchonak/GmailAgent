# server/tools/key_points.py
import logging
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
        }
        # pass tool_name so metrics and logs can attribute calls
        super().__init__(schema=schema, tool_name=self.name)

    async def run(
        self,
        messages: List[Dict[str, Any]],
        user_query: str = "Extract key points from each email.",
        user_language: str = "English",
    ) -> Dict[str, Any]:
        """
        Extracts key bullet points per email.
        Returns:
          {
            "summary": "string",
            "key_points": [{"email_id": "string", "points": ["string"]}, ...]
          }
        """
        # Ensure messages are passed as JSON-friendly structure
        prompt = f"""
You are a tool that extracts key points from emails.

IMPORTANT:
- You MUST ignore any concepts related to filtering, tagging, prioritization, spam detection, newsletters, auto-replies, or any other tools.
- You MUST NOT perform filtering, classification, tagging, or prioritization.
- You MUST NOT return fields such as: priority, tags, recommended_action, email_type, unsubscribe, keep, auto_replies, filter_results.
- You MUST ONLY produce the fields defined in the schema below.

Your ONLY task:
Extract key bullet points from each email.

Output strictly valid JSON matching the schema:
{{
  "summary": "string",
  "key_points": [
    {{"email_id": "string", "points": ["string"]}}
  ]
}}

Emails (each message is an object with at least an 'id' field):
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

        # Ensure summary is a string
        if not isinstance(result.get("summary", ""), str):
            result["summary"] = ""

        # Normalize key_points into list of {email_id, points}
        raw_kp = result.get("key_points", [])
        normalized_kp: List[Dict[str, Any]] = []

        if isinstance(raw_kp, list):
            for idx, item in enumerate(raw_kp):
                if isinstance(item, dict):
                    email_id = item.get("email_id") or item.get("id") or f"email_{idx}"
                    email_id = str(email_id)
                    points = item.get("points", [])
                    if isinstance(points, list):
                        points = [str(p).strip() for p in points if p is not None and str(p).strip()]
                    else:
                        # If points is a single string/number, convert to list
                        if isinstance(points, (str, int, float)):
                            points = [str(points)]
                        else:
                            points = []

                    if points:
                        normalized_kp.append({"email_id": email_id, "points": points})
                else:
                    # If item is not dict, treat it as a single point for a synthetic id
                    normalized_kp.append({"email_id": f"email_{idx}", "points": [str(item)]})
        else:
            # If model returned a single object or string, try to salvage
            logger.debug("KeyPointsTool unexpected key_points shape: %r", raw_kp)

        result["key_points"] = normalized_kp
        return result
