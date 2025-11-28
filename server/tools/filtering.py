import logging
from typing import Dict, Any, List
from .base import BaseTool

logger = logging.getLogger(__name__)

class FilteringTool(BaseTool):
    name = "filtering"

    def __init__(self):
        # Совместимо с FilteredEmail моделью
        schema = {
            "filter_results": [
                {
                    "id": "string",
                    "subject": "string",
                    "body": "string",
                    "tags": ["string"],
                    "priority": "string",              # low | medium | high
                    "recommended_action": "string",    # ignore | read | reply | unsubscribe | save
                }
            ],
            "summary": "string"
        }
        super().__init__(schema=schema)

    async def run(
        self,
        messages: List[Dict[str, Any]],
        user_language: str = "English"
    ) -> Dict[str, Any]:
        prompt = (
            f"You are an agent for email filtering and prioritization.\n"
            f"Task: Analyze each email individually.\n\n"
            f"Output ONLY valid JSON matching the schema below.\n"
            f"DO NOT include explanations, text outside JSON, or Markdown fences.\n"
            f"Language: {user_language}\n\n"
            f"Schema:\n"
            f"{{\n"
            f"  \"filter_results\": [\n"
            f"    {{\"id\": \"string\", \"subject\": \"string\", \"body\": \"string\", \"tags\": [\"string\"], \"priority\": \"string\", \"recommended_action\": \"string\"}}\n"
            f"  ],\n"
            f"  \"summary\": \"string\"\n"
            f"}}\n\n"
            f"Rules:\n"
            f"- For EACH email in the input list, return ONE object with fields id, subject, body, tags[], priority, recommended_action.\n"
            f"- Place ALL objects inside the 'filter_results' array.\n"
            f"- Do NOT merge multiple emails into one block.\n"
            f"- 'summary' must be a short overview of the filtering process, not the full content.\n"
            f"- Priority: 'high' if urgent or deadline; 'medium' if requires attention; 'low' otherwise.\n"
            f"- Recommended_action: reply/read/unsubscribe/save/ignore.\n"
            f"- Tags: derive from sender or content.\n\n"
            f"Emails:\n{messages}"
        )

        result = await self.call(
            prompt,
            variables={"emails": messages},
            user_language=user_language
        )

        # --- Защитная нормализация ---
        if not isinstance(result, dict):
            logger.warning("FilteringTool result is not a dict, forcing empty structure")
            result = {}
        if not isinstance(result.get("filter_results"), list):
            logger.warning("FilteringTool result missing 'filter_results' list, forcing empty list")
            result["filter_results"] = []
        if not isinstance(result.get("summary"), str):
            result["summary"] = (
                "Фильтрация завершена." if user_language.lower().startswith("rus")
                else "Filtering complete."
            )

        # Нормализуем каждую карточку
        normalized = []
        for idx, v in enumerate(result["filter_results"]):
            if isinstance(v, dict):
                normalized.append({
                    "id": v.get("id", str(idx + 1)),
                    "subject": v.get("subject", ""),
                    "body": v.get("body", ""),
                    "tags": v.get("tags", []) if isinstance(v.get("tags"), list) else [],
                    "priority": v.get("priority", "low"),
                    "recommended_action": v.get("recommended_action", "ignore"),
                })
            else:
                normalized.append({
                    "id": str(idx + 1),
                    "subject": "",
                    "body": str(v),
                    "tags": [],
                    "priority": "low",
                    "recommended_action": "ignore",
                })

        result["filter_results"] = normalized
        return result
