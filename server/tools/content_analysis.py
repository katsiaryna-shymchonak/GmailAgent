
from typing import Dict, Any, List
from .base import BaseTool

class ContentAnalysisTool(BaseTool):
    name = "content_analysis"

    def __init__(self):
        schema = {
            "summary": "string",
            "key_tasks": [{"email_id": "string", "task": "string"}],
            "deadlines": [{"email_id": "string", "deadline": "string"}],
            "draft_reply": {"string": "string"}  # email_id -> reply_text
        }
        super().__init__(schema=schema)

    async def run(
        self,
        messages: List[Dict[str, Any]],
        user_query: str,
        user_language: str = "English"
    ) -> Dict[str, Any]:
        prompt = (
            f"You are an agent for email content analysis.\n"
            f"Task: {user_query}\n\n"
            f"Output strictly valid JSON matching the schema.\n"
            f"Language: {user_language}\n\n"
            f"Rules:\n"
            f"- Summarize only actual content from provided emails.\n"
            f"- Identify key points and extract actionable tasks only if explicit.\n"
            f"- Extract deadlines only if explicitly present.\n"
            f"- Return:\n"
            f"  - summary: short overview.\n"
            f"  - key_tasks: list of objects {{email_id, task}}.\n"
            f"  - deadlines: list of objects {{email_id, deadline}}.\n"
            f"  - draft_reply: dictionary of {{email_id: short_reply}}; if no per-email replies, include a single {{\"generic\": reply}}.\n\n"
            f"Emails:\n{messages}"
        )

        # Вызов модели через BaseTool.call — строго через variables
        result = await self.call(
            prompt,
            variables={"query": user_query, "messages": messages},
            user_language=user_language
        )

        # Defensive normalization
        if not isinstance(result, dict):
            result = {}
        result.setdefault("summary", "")
        result.setdefault("key_tasks", [])
        result.setdefault("deadlines", [])

        dr = result.get("draft_reply")
        if isinstance(dr, str):
            result["draft_reply"] = {"generic": dr}
        elif not isinstance(dr, dict):
            result["draft_reply"] = {"generic": (
                "Спасибо за информацию. Ознакомлюсь и отвечу позже."
                if user_language.lower().startswith("rus")
                else "Thank you for the information. I will review and follow up."
            )}

        return result
