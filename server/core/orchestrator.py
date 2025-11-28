import logging
import json
from typing import Dict, Any, List

from ..core.executor import PlanExecutor
from ..tools import FilteringTool, ContentAnalysisTool, NewsletterTool, AutoReplyTool, BaseTool
from .reviewers import QualityReviewer
from ..config.settings import get_settings
from ..services.database import store_email_memory

logger = logging.getLogger(__name__)
settings = get_settings()


def detect_language(query: str, messages: List[Any]) -> str:
    """Определяем язык по query и содержимому писем."""
    total_chars = 0
    cyrillic_chars = 0
    for msg in messages:
        subject = getattr(msg, "subject", "") if not isinstance(msg, dict) else msg.get("subject", "")
        body = getattr(msg, "body", "") if not isinstance(msg, dict) else msg.get("body", "")
        text = str(subject) + str(body)

        total_chars += len(text)
        cyrillic_chars += sum(1 for ch in text if "\u0400" <= ch <= "\u04FF")

    if cyrillic_chars > 0 and (cyrillic_chars / max(total_chars, 1)) > 0.6:
        return "Russian"
    if query and any("\u0400" <= ch <= "\u04FF" for ch in query):
        return "Russian"
    return "English"


class AgentOrchestrator:
    """Coordinates planning, execution, review, and memory persistence."""

    def __init__(self):
        self.filter_tool = FilteringTool()
        self.content_tool = ContentAnalysisTool()
        self.newsletter_tool = NewsletterTool()
        self.auto_reply_tool = AutoReplyTool()
        self.capabilities_tip = None
        # Планировщик через LLM
        self.planner = BaseTool(schema={"plan": ["string"]})
        # Ревьювер
        self.reviewer = QualityReviewer()

    async def _decide_plan(self, query: str, user_language: str = "English") -> List[str]:
        """Определение плана через LLM вместо ключевых слов."""
        prompt = (
            f"You are a planning agent.\n"
            f"Task: Decide which tool should handle the user's request.\n\n"
            f"Available tools:\n"
            f"- filter: for prioritization, tags, spam detection\n"
            f"- content: for summarization, key points, tasks, deadlines\n"
            f"- newsletter: for unsubscribe, digest, weekly reports\n"
            f"- auto: for auto-replies and draft responses\n\n"
            f"User query: {query}\n\n"
            f"Output strictly valid JSON: {{\"plan\": [\"tool_name\"]}}"
        )
        try:
            result = await self.planner.call(prompt, variables={"query": query}, user_language=user_language)
            if isinstance(result, dict) and "plan" in result and isinstance(result["plan"], list):
                return result["plan"]
        except Exception as e:
            logger.error("Planner failed: %s", e)
        return []

    def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Приводим результат к контракту AnalyzeResponse."""
        dr = result.get("draft_reply")
        if isinstance(dr, str):
            result["draft_reply"] = {"generic": dr}
        elif not isinstance(dr, dict):
            result["draft_reply"] = {}

        kt = result.get("key_tasks", [])
        normalized_kt: List[Dict[str, str]] = []
        if isinstance(kt, list):
            for idx, item in enumerate(kt):
                if isinstance(item, str):
                    normalized_kt.append({"email_id": f"task_{idx}", "task": item})
                elif isinstance(item, dict):
                    normalized_kt.append({
                        "email_id": item.get("email_id", f"task_{idx}"),
                        "task": item.get("task", "")
                    })
        result["key_tasks"] = normalized_kt

        dl = result.get("deadlines", [])
        normalized_dl: List[Dict[str, str]] = []
        if isinstance(dl, list):
            for idx, item in enumerate(dl):
                if isinstance(item, str):
                    normalized_dl.append({"email_id": f"deadline_{idx}", "deadline": item})
                elif isinstance(item, dict):
                    normalized_dl.append({
                        "email_id": item.get("email_id", f"deadline_{idx}"),
                        "deadline": item.get("deadline", "")
                    })
        result["deadlines"] = normalized_dl

        ni = result.get("newsletter_insights")
        if not isinstance(ni, dict):
            ni = {}
        ni.setdefault("unsubscribe", [])
        ni.setdefault("keep", [])
        ni.setdefault("digest", "")
        ni.setdefault("weekly_report", None)
        result["newsletter_insights"] = ni

        result.pop("capabilities_tip", None)
        return result

    async def initial_summary(
        self,
        messages: List[Any],
        query: str = "Summarize the selected emails and highlight key points.",
        sender_email: str | None = None,
    ) -> Dict[str, Any]:
        """Первичный анализ: всегда только контент‑тул."""
        user_language = detect_language(query, messages)

        executor = PlanExecutor(
            filter_tool=self.filter_tool,
            newsletter_tool=self.newsletter_tool,
            content_tool=self.content_tool,
            auto_reply_tool=self.auto_reply_tool,
            capabilities_tip=self.capabilities_tip,
        )
        result = await executor.run_plan(messages, ["content"], query, user_language=user_language)
        result = self._normalize_result(result)

        # вызов ревьювера
        score = await self.reviewer.score(result)
        if score < 7:
            result = await self.reviewer.refine(result)

        if "summary" in result and messages:
            try:
                records = [msg.dict() if hasattr(msg, "dict") else msg for msg in messages]
                store_email_memory(records)
            except Exception as e:
                logger.error("Failed to store emails in memory: %s", e)

        logger.info("Initial summary result → %s", json.dumps(result, ensure_ascii=False, indent=2))
        return result

    async def follow_up(
        self,
        messages: List[Any],
        query: str,
        sender_email: str | None = None,
    ) -> Dict[str, Any]:
        user_language = detect_language(query, messages)

        plan = await self._decide_plan(query, user_language=user_language)
        logger.info("Follow-up execution plan → %s", plan)

        if not plan:
            return {"summary": "", "messages": [{"role": "agent", "tool": "system", "content": "No relevant tool detected."}]}

        executor = PlanExecutor(
            filter_tool=self.filter_tool,
            newsletter_tool=self.newsletter_tool,
            content_tool=self.content_tool,
            auto_reply_tool=self.auto_reply_tool,
            capabilities_tip=self.capabilities_tip,
        )
        result = await executor.run_plan(messages, plan, query, user_language=user_language)
        result = self._normalize_result(result)

        # ── вызов ревьювера ──
        score = await self.reviewer.score(result)
        if score < 7:
            result = await self.reviewer.refine(result)

        logger.info("Follow-up result → %s", json.dumps(result, ensure_ascii=False, indent=2))
        return result
