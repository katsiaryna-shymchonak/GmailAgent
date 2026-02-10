# server/core/orchestrator.py
import asyncio
import logging
import json
from typing import Dict, Any, List, Optional

from ..core.executor import PlanExecutor
from ..tools import (
    FilteringTool,
    ContentAnalysisTool,
    NewsletterTool,
    AutoReplyTool,
)
from ..tools.key_points import KeyPointsTool
from ..tools.deadline_tool import DeadlineTool
from .reviewers import QualityReviewer
from .planner import PlanBuilder
from ..config.settings import get_settings
from ..services.database import (
    save_active_emails,
    load_active_emails,
    init_active_emails_table,
)

logger = logging.getLogger(__name__)
settings = get_settings()


def detect_language(query: str, messages: List[Any]) -> str:
    total_chars = 0
    cyrillic_chars = 0

    for msg in messages:
        subject = ""
        body = ""

        if isinstance(msg, dict):
            subject = msg.get("subject", "") or ""
            body = msg.get("body", "") or ""
        else:
            subject = getattr(msg, "subject", "") or ""
            body = getattr(msg, "body", "") or ""

        text = str(subject) + str(body)
        total_chars += len(text)
        cyrillic_chars += sum(1 for ch in text if "\u0400" <= ch <= "\u04FF")

    if cyrillic_chars > 0 and (cyrillic_chars / max(total_chars, 1)) > 0.6:
        return "Russian"

    if query and any("\u0400" <= ch <= "\u04FF" for ch in query):
        return "Russian"

    return "English"


def _is_summary_only_query(query: str) -> bool:
    if not query or not isinstance(query, str):
        return False

    q = query.strip().lower()

    tokens = {
        "summary_only",
        "just_summary",
        "summary only",
        "__summary_only__",
        "only_summary",
        "только summary",
        "только саммари",
        "только сводка",
    }

    if q in tokens:
        return True

    if ("summary" in q and ("only" in q or "только" in q)) or (
        "сводка" in q and "только" in q
    ):
        return True

    if q.startswith("summary:") and "only" in q:
        return True

    return False


class AgentOrchestrator:
    """
    Central orchestrator for email analysis.
    Clean production variant (minimal logs, no noise).
    """

    def __init__(self):
        try:
            init_active_emails_table()
        except Exception:
            logger.exception("Failed to ensure active_emails table exists")

        # Tools
        self.filter_tool = FilteringTool()
        self.content_tool = ContentAnalysisTool()
        self.newsletter_tool = NewsletterTool()
        self.key_points_tool = KeyPointsTool()
        self.auto_reply_tool = AutoReplyTool()
        self.deadline_tool = DeadlineTool()

        self.capabilities_tip = None

        # Planner
        self.plan_builder = PlanBuilder()

        # Reviewer (methods enabled, calls disabled)
        self.reviewer = QualityReviewer()

        # Allowed tools
        self.allowed_tools = {
            "filter",
            "content",
            "key_points",
            "newsletter",
            "auto",
            "deadlines",
        }

    async def _review_summary(self, summary_text: str) -> str:
        try:
            score = await self.reviewer.score({"summary": summary_text})
            if not isinstance(score, int):
                import re
                m = re.search(r"(\d+)", str(score))
                score = int(m.group(1)) if m else 10
        except Exception:
            score = 10

        if score < 7:
            try:
                refined = await self.reviewer.refine({"summary": summary_text})
                summary_text = refined.get("summary", summary_text)
            except Exception:
                pass

        return summary_text

    async def _review_full_result(self, merged: Dict[str, Any]) -> Dict[str, Any]:
        try:
            score = await self.reviewer.score(merged)
            if not isinstance(score, int):
                import re
                m = re.search(r"(\d+)", str(score))
                score = int(m.group(1)) if m else 10
        except Exception:
            score = 10

        if score < 7:
            try:
                merged = await self.reviewer.refine(merged)
            except Exception:
                logger.exception("Reviewer refine failed")

        return merged

    @staticmethod
    def _to_serializable_message(msg: Any) -> Dict[str, Any]:
        if isinstance(msg, dict):
            return dict(msg)

        if hasattr(msg, "dict") and callable(getattr(msg, "dict")):
            try:
                return msg.dict()
            except Exception:
                pass

        out: Dict[str, Any] = {}
        for attr in ("id", "message_id", "gmail_id", "subject", "body", "date", "from", "to"):
            try:
                val = getattr(msg, attr, None)
                if val is not None:
                    out[attr] = val
            except Exception:
                continue

        try:
            if not out and hasattr(msg, "__dict__"):
                out = dict(msg.__dict__)
        except Exception:
            pass

        return out

    def _ensure_ids(self, messages: List[Any]) -> List[Dict[str, Any]]:
        normalized = []
        for idx, msg in enumerate(messages):
            m = self._to_serializable_message(msg)

            if "id" not in m or not m.get("id"):
                for alt in ("message_id", "gmail_id", "msg_id"):
                    if alt in m and m.get(alt):
                        m["id"] = m.get(alt)
                        break

            if "id" not in m or not m.get("id"):
                m["id"] = f"email_{idx}"

            normalized.append(m)

        return normalized

    def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        # --- KEY TASKS ---
        kt = result.get("key_tasks", [])
        normalized_kt = []
        for idx, item in enumerate(kt):
            if isinstance(item, str):
                normalized_kt.append({
                    "email_id": f"task_{idx}",
                    "task": item
                })
            elif isinstance(item, dict):
                normalized_kt.append({
                    "email_id": item.get("email_id", f"task_{idx}"),
                    "task": item.get("task", "")
                })
        result["key_tasks"] = normalized_kt

        # --- DEADLINES ---
        dl = result.get("deadlines", [])
        normalized_dl = []
        for idx, item in enumerate(dl):
            if isinstance(item, str):
                normalized_dl.append({
                    "email_id": f"deadline_{idx}",
                    "deadline": item,
                    "description": ""
                })
            elif isinstance(item, dict):
                normalized_dl.append({
                    "email_id": item.get("email_id", f"deadline_{idx}"),
                    "deadline": item.get("deadline", ""),
                    "description": item.get("description", "")
                })
        result["deadlines"] = normalized_dl

        # --- KEY POINTS ---
        kp = result.get("key_points", [])
        normalized_kp = []
        for idx, item in enumerate(kp):
            if isinstance(item, dict):
                pts = item.get("points", [])
                if isinstance(pts, str):
                    pts = [pts]
                elif not isinstance(pts, list):
                    pts = []
                normalized_kp.append({
                    "email_id": item.get("email_id", f"email_{idx}"),
                    "points": pts
                })
        result["key_points"] = normalized_kp

        # --- NEWSLETTER ---
        ni = result.get("newsletter_insights")
        if not isinstance(ni, dict):
            ni = {}
        ni.setdefault("unsubscribe", [])
        ni.setdefault("keep", [])
        ni.setdefault("digest", "")
        ni.setdefault("weekly_report", None)
        result["newsletter_insights"] = ni

        return result

    async def initial_summary(
        self,
        messages: List[Any],
        query: str = "Summarize the selected emails and highlight key points.",
        sender_email: Optional[str] = None,
    ) -> Dict[str, Any]:

        user_language = detect_language(query, messages)
        session_id = sender_email or "default"

        try:
            records = self._ensure_ids(messages)
            save_active_emails(session_id, records)
        except Exception:
            logger.exception("Failed to save active emails")

        executor = PlanExecutor(
            filter_tool=self.filter_tool,
            newsletter_tool=self.newsletter_tool,
            content_tool=self.content_tool,
            key_points_tool=self.key_points_tool,
            auto_reply_tool=self.auto_reply_tool,
            deadline_tool=self.deadline_tool,
            capabilities_tip=self.capabilities_tip,
        )

        try:
            result = await executor.run_plan(
                messages, ["content"], query, user_language=user_language
            )
        except Exception:
            logger.exception("Initial content run failed")
            return {"summary": ""}

        raw_summary = result.get("summary", "")
        if isinstance(raw_summary, str):
            summary_text = raw_summary
        elif isinstance(raw_summary, list):
            summary_text = " ".join(str(x) for x in raw_summary)
        elif isinstance(raw_summary, dict):
            summary_text = raw_summary.get("summary") or json.dumps(raw_summary, ensure_ascii=False)
        else:
            summary_text = ""

        # Reviewer disabled:
        # summary_text = await self._review_summary(summary_text)

        try:
            records = self._ensure_ids(messages)
        except Exception:
            logger.exception("Failed to store emails in memory")

        return {"summary": summary_text}

    async def follow_up(
        self,
        messages: List[Any],
        query: str,
        sender_email: Optional[str] = None,
        mode: str = "sequential",
    ) -> Dict[str, Any]:

        user_language = detect_language(query, messages)
        session_id = sender_email or "default"

        try:
            active_messages = messages or load_active_emails(session_id)
        except Exception:
            logger.exception("Failed to load active emails")
            active_messages = []

        if not active_messages:
            return {
                "summary": "",
                "messages": [
                    {
                        "role": "agent",
                        "tool": "system",
                        "content": "No active emails. Please send selected emails to the agent first.",
                    }
                ],
            }

        active_messages = self._ensure_ids(active_messages)

        # Summary-only shortcut
        if _is_summary_only_query(query):
            plan = ["content"]
        else:
            plan = await self.plan_builder.build_plan(query=query, user_language=user_language)
            plan = [p for p in plan if p in self.allowed_tools]

        if not plan:
            return {
                "summary": "",
                "messages": [
                    {
                        "role": "agent",
                        "tool": "system",
                        "content": "No relevant tool detected.",
                    }
                ],
            }

        executor = PlanExecutor(
            filter_tool=self.filter_tool,
            newsletter_tool=self.newsletter_tool,
            content_tool=self.content_tool,
            key_points_tool=self.key_points_tool,
            auto_reply_tool=self.auto_reply_tool,
            deadline_tool=self.deadline_tool,
            capabilities_tip=self.capabilities_tip,
        )

        results: List[Dict[str, Any]] = []

        if mode == "single":
            tool = plan[0]
            try:
                res = await executor.run_plan(
                    active_messages, [tool], query, user_language=user_language
                )
            except Exception:
                logger.exception("Tool failed in single mode")
                res = {}
            results.append(res)

        elif mode == "parallel":
            async def run_one(t):
                try:
                    return await executor.run_plan(
                        active_messages, [t], query, user_language=user_language
                    )
                except Exception:
                    logger.exception("Tool failed in parallel mode")
                    return {}

            tasks = [run_one(t) for t in plan]
            results = await asyncio.gather(*tasks)

        else:  # sequential
            for t in plan:
                try:
                    res = await executor.run_plan(
                        active_messages, [t], query, user_language=user_language
                    )
                except Exception:
                    logger.exception("Tool failed in sequential mode")
                    res = {}
                results.append(res)

        merged: Dict[str, Any] = {
            "summary": "",
            "key_tasks": [],
            "deadlines": [],
            "key_points": [],
            "filter_results": [],
            "newsletter_insights": {},
            "auto_replies": [],
            "messages": [],
        }

        for idx, res in enumerate(results):
            if not isinstance(res, dict):
                continue

            if not merged["summary"]:
                s = res.get("summary")
                if isinstance(s, str) and s.strip():
                    merged["summary"] = s.strip()

            for list_key in ("key_tasks", "deadlines", "key_points", "filter_results", "auto_replies"):
                val = res.get(list_key)
                if isinstance(val, list):
                    merged[list_key].extend(val)

            ni = res.get("newsletter_insights")
            if isinstance(ni, dict):
                merged["newsletter_insights"].update(ni)

            msgs = res.get("messages")
            if isinstance(msgs, list) and msgs:
                merged["messages"].extend(msgs)
            else:
                merged["messages"].append({
                    "role": "agent",
                    "tool": plan[idx] if idx < len(plan) else "unknown",
                    "content": res.get("summary", ""),
                })

        def dedupe_list(items: List[Any]) -> List[Any]:
            seen = set()
            out = []
            for it in items:
                try:
                    if isinstance(it, dict):
                        key = tuple(sorted((k, str(v)) for k, v in it.items()))
                    else:
                        key = str(it)
                except Exception:
                    key = str(it)
                if key not in seen:
                    seen.add(key)
                    out.append(it)
            return out

        for k in ("key_tasks", "deadlines", "key_points", "filter_results", "auto_replies"):
            merged[k] = dedupe_list(merged[k])

        # Collect executed tools
        executed = []
        for r in results:
            if isinstance(r, dict):
                tools = r.get("executed_tools", [])
                if isinstance(tools, list):
                    executed.extend(tools)

        seen = set()
        executed_unique = []
        for t in executed:
            if t not in seen:
                seen.add(t)
                executed_unique.append(t)

        merged["executed_tools"] = executed_unique

        merged = self._normalize_result(merged)

        # Reviewer disabled:
        # merged = await self._review_full_result(merged)

        return merged

    async def analyze_emails(
        self,
        messages: List[Any],
        query: Optional[str],
        sender_email: Optional[str],
    ) -> Dict[str, Any]:
        return await self.initial_summary(
            messages,
            query=query or "Summarize the selected emails.",
            sender_email=sender_email,
        )
