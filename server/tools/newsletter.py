# server/tools/newsletter_tool.py
import logging
from typing import Dict, Any, List
from .base import BaseTool

logger = logging.getLogger(__name__)


class NewsletterTool(BaseTool):
    name = "newsletter"

    def __init__(self):
        # Strict schema matching NewsletterInsights
        schema = {
            "unsubscribe": ["string"],
            "keep": ["string"],
            "digest": "string",
            "weekly_report": "string"
        }
        super().__init__(schema=schema, tool_name=self.name)

    # -----------------------------
    # Helpers
    # -----------------------------
    def _label_for(self, msg: Dict[str, Any]) -> str:
        """Human-readable label: 'Sender — Subject'."""
        sender = (msg.get("from") or msg.get("from_") or "").strip()
        subject = (msg.get("subject") or "").strip()

        if sender and subject:
            return f"{sender} — {subject}"
        return sender or subject or "Unknown newsletter"

    def _is_newsletter(self, msg: Dict[str, Any]) -> bool:
        """Simple heuristic: detect newsletters."""
        subject = (msg.get("subject") or "").lower()
        snippet = (msg.get("snippet") or "").lower()
        sender = (msg.get("from") or msg.get("from_") or "").lower()

        keywords = [
            "newsletter", "digest", "рассылка", "дайджест",
            "подборка", "подписка", "subscription", "update"
        ]

        return any(k in subject for k in keywords) or \
               any(k in snippet for k in keywords) or \
               "no-reply" in sender or "noreply" in sender

    # -----------------------------
    # Main run method
    # -----------------------------
    async def run(
        self,
        messages: List[Dict[str, Any]],
        filter_data: Dict[str, Any],
        weekly_metrics: Dict[str, Any],
        user_language: str = "English"
    ) -> Dict[str, Any]:

        # Select only newsletter-like messages
        newsletter_msgs = [m for m in messages if self._is_newsletter(m)]

        # Prepare prompt for LLM
        prompt = f"""
You are a newsletter analysis tool.

LANGUAGE:
- Respond strictly in {user_language}.

TASK:
Analyze the provided emails and classify newsletters into:
- "unsubscribe": newsletters the user should unsubscribe from
- "keep": newsletters the user should keep
- "digest": a short summary of useful newsletters
- "weekly_report": a concise weekly insight

RULES:
- Output strictly valid JSON matching the schema.
- "unsubscribe" and "keep" must be arrays of plain strings.
- Each string must be a human-readable label: "Sender — Subject".
- Do NOT output objects, only strings.
- If no newsletters exist, return empty arrays and empty strings.

Schema:
{{
  "unsubscribe": ["string"],
  "keep": ["string"],
  "digest": "string",
  "weekly_report": "string"
}}

Emails:
{newsletter_msgs}
"""

        # Call LLM
        result = await self.call(
            prompt,
            variables={"messages": newsletter_msgs},
            user_language=user_language
        )

        # Defensive normalization
        if not isinstance(result, dict):
            result = {}

        unsubscribe = result.get("unsubscribe", [])
        keep = result.get("keep", [])
        digest = result.get("digest", "")
        weekly_report = result.get("weekly_report", "")

        # Normalize lists
        def normalize_list(items):
            out = []
            for item in items or []:
                if isinstance(item, str) and item.strip():
                    out.append(item.strip())
                else:
                    # If LLM returned dict or something else — convert to label
                    try:
                        label = self._label_for(item)
                        out.append(label)
                    except Exception:
                        out.append(str(item))
            return out

        unsubscribe = normalize_list(unsubscribe)
        keep = normalize_list(keep)

        # Fallbacks
        if not digest:
            digest = (
                "Нет полезных рассылок." if user_language.lower().startswith("rus")
                else "No useful newsletters identified."
            )

        if not weekly_report:
            weekly_report = (
                "Еженедельный отчёт: недостаточно данных."
                if user_language.lower().startswith("rus")
                else "Weekly report: insufficient data."
            )

        return {
            "unsubscribe": unsubscribe,
            "keep": keep,
            "digest": digest,
            "weekly_report": weekly_report,
        }
