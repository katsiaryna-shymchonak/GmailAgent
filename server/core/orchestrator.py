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
    BaseTool,
)
from ..tools.key_points import KeyPointsTool
from ..tools.deadline_tool import DeadlineTool
from .reviewers import QualityReviewer
from ..config.settings import get_settings
from ..services.database import (
    store_email_memory,
    save_active_emails,
    load_active_emails,
    init_active_emails_table,
)

logger = logging.getLogger(__name__)
settings = get_settings()


def detect_language(query: str, messages: List[Any]) -> str:
    """Определяем язык по query и содержимому писем."""
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
    """Определяет, просит ли пользователь только summary (варианты на русском и английском)."""
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
        "только summary",
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

    Behavior:
      - initial_summary: saves active emails and runs ONLY content (summary-only)
      - follow_up: planner decides which tool(s) to run; supports single/sequential/parallel modes
      - merges results, normalizes output, runs reviewer
    """

    def __init__(self):
        # Ensure active emails table exists
        try:
            init_active_emails_table()
        except Exception:
            logger.exception("Failed to ensure active_emails table exists")

        # Tools
        self.filter_tool = FilteringTool()
        self.content_tool = ContentAnalysisTool()  # summary-only tool
        self.newsletter_tool = NewsletterTool()
        self.key_points_tool = KeyPointsTool()
        self.auto_reply_tool = AutoReplyTool()
        self.deadline_tool = DeadlineTool()
        self.capabilities_tip = None

        # Planner: BaseTool used as LLM interface for planning
        self.planner = BaseTool(schema={"plan": ["string"]}, tool_name="planner")

        # Reviewer
        self.reviewer = QualityReviewer()

        # Allowed tools and safety limits
        self.allowed_tools = {
            "filter",
            "content",
            "key_points",
            "newsletter",
            "auto",
            "deadlines",
        }
        self.max_tools = 3  # safety limit to avoid burning quota

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    @staticmethod
    def _to_serializable_message(msg: Any) -> Dict[str, Any]:
        """
        Преобразует сообщение в словарь. Поддерживает dict, pydantic-like objects и простые объекты.
        Не удаляет поля, только копирует в dict.
        """
        if isinstance(msg, dict):
            return dict(msg)
        if hasattr(msg, "dict") and callable(getattr(msg, "dict")):
            try:
                return msg.dict()
            except Exception:
                # fallback to attribute extraction
                pass
        # Generic object fallback: try to extract common attributes
        out: Dict[str, Any] = {}
        for attr in ("id", "message_id", "gmail_id", "subject", "body", "date", "from", "to"):
            try:
                val = getattr(msg, attr, None)
                if val is not None:
                    out[attr] = val
            except Exception:
                continue
        # If still empty, try __dict__
        try:
            if not out and hasattr(msg, "__dict__"):
                out = dict(msg.__dict__)
        except Exception:
            pass
        return out

    def _ensure_ids(self, messages: List[Any]) -> List[Dict[str, Any]]:
        """
        Гарантирует, что у каждого сообщения есть поле 'id'.
        Если реального id нет, генерирует внутренний уникальный идентификатор email_{index}.
        Возвращает список словарей.
        """
        normalized: List[Dict[str, Any]] = []
        for idx, msg in enumerate(messages):
            m = self._to_serializable_message(msg)
            # Normalize common alternative id fields
            if "id" not in m or not m.get("id"):
                for alt in ("message_id", "gmail_id", "msg_id"):
                    if alt in m and m.get(alt):
                        m["id"] = m.get(alt)
                        break
            if "id" not in m or not m.get("id"):
                m["id"] = f"email_{idx}"
            normalized.append(m)
        return normalized

    # -------------------------------------------------------------------------
    # Planner via LLM
    # -------------------------------------------------------------------------
    async def _decide_plan(self, query: str, user_language: str = "English") -> List[str]:
        """Определяет набор инструментов на основе анализа интента пользователя."""
        if _is_summary_only_query(query):
            return ["content"]

        prompt = (
            f"You are a planning agent for an email assistant.\n"
            f"Available tools: {list(self.allowed_tools)}\n"
            f"User query: {query}\n"
            f"Decision Rules:\n"
            f"1. If the user asks for key points, tasks, action items, or 'главное', include 'key_points'.\n"
            f"2. If the user asks for deadlines or dates, include 'deadlines'.\n"
            f"3. Use 'content' for general overviews.\n"
            f"Output ONLY JSON: {{\"plan\": [\"tool_name\"]}}"
        )
        try:
            result = await self.planner_llm.call(prompt, user_language=user_language)
            if isinstance(result, dict) and "plan" in result:
                plan = [p.strip() for p in result["plan"] if p.strip() in self.allowed_tools]
                return plan[:self.max_tools]
        except Exception as e:
            logger.error("Planner failed: %s", e)
        return ["content"]

    # -------------------------------------------------------------------------
    # Normalize result to AnalyzeResponse contract
    # -------------------------------------------------------------------------
    def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize result to the AnalyzeResponse contract."""
        kt = result.get("key_tasks", [])
        normalized_kt: List[Dict[str, str]] = []
        if isinstance(kt, list):
            for idx, item in enumerate(kt):
                if isinstance(item, str):
                    normalized_kt.append({"email_id": f"task_{idx}", "task": item})
                elif isinstance(item, dict):
                    normalized_kt.append(
                        {
                            "email_id": item.get("email_id", f"task_{idx}"),
                            "task": item.get("task", ""),
                        }
                    )
        result["key_tasks"] = normalized_kt

        dl = result.get("deadlines", [])
        normalized_dl: List[Dict[str, str]] = []
        if isinstance(dl, list):
            for idx, item in enumerate(dl):
                if isinstance(item, str):
                    normalized_dl.append({"email_id": f"deadline_{idx}", "deadline": item})
                elif isinstance(item, dict):
                    normalized_dl.append(
                        {
                            "email_id": item.get("email_id", f"deadline_{idx}"),
                            "deadline": item.get("deadline", ""),
                        }
                    )
        result["deadlines"] = normalized_dl

        # Normalize key_points
        kp = result.get("key_points", [])
        normalized_kp: List[Dict[str, Any]] = []
        if isinstance(kp, list):
            for idx, item in enumerate(kp):
                if isinstance(item, dict):
                    normalized_kp.append(
                        {
                            "email_id": item.get("email_id", f"email_{idx}"),
                            "points": item.get("points", [])
                            if isinstance(item.get("points", []), list)
                            else [],
                        }
                    )
        result["key_points"] = normalized_kp

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

    # -------------------------------------------------------------------------
    # INITIAL SUMMARY — save active emails and run ONLY content
    # -------------------------------------------------------------------------
    async def initial_summary(
        self,
        messages: List[Any],
        query: str = "Summarize the selected emails and highlight key points.",
        sender_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Primary analysis: save active emails and return ONLY summary."""
        user_language = detect_language(query, messages)
        session_id = sender_email or "default"

        # Save active emails (serializable dicts) and ensure ids
        try:
            records = self._ensure_ids(messages)
            save_active_emails(session_id, records)
        except Exception as e:
            logger.error("Failed to save active emails: %s", e)

        executor = PlanExecutor(
            filter_tool=self.filter_tool,
            newsletter_tool=self.newsletter_tool,
            content_tool=self.content_tool,
            key_points_tool=self.key_points_tool,
            auto_reply_tool=self.auto_reply_tool,
            deadline_tool=self.deadline_tool,
            capabilities_tip=self.capabilities_tip,
        )

        # Run only content (summary-only)
        try:
            result = await executor.run_plan(
                messages, ["content"], query, user_language=user_language
            )
        except Exception as e:
            logger.error("Initial content run failed: %s", e)
            return {"summary": ""}

        # Normalize summary into a single string
        raw_summary = result.get("summary", "")
        if isinstance(raw_summary, str):
            summary_text = raw_summary
        elif isinstance(raw_summary, list):
            if raw_summary and isinstance(raw_summary[0], dict) and "summary" in raw_summary[0]:
                parts = []
                for item in raw_summary:
                    eid = item.get("email_id") or item.get("id") or ""
                    s = item.get("summary") or item.get("text") or ""
                    if eid:
                        parts.append(f"{eid}: {s}")
                    else:
                        parts.append(str(s))
                summary_text = "  ".join(parts)
            else:
                summary_text = " ".join([str(x) for x in raw_summary])
        elif isinstance(raw_summary, dict):
            summary_text = raw_summary.get("summary") or json.dumps(raw_summary, ensure_ascii=False)
        else:
            summary_text = ""

        # Reviewer: score and optional refine (DISABLED)
        # try:
        #     score = await self.reviewer.score({"summary": summary_text})
        #     if not isinstance(score, int):
        #         try:
        #             import re
        #             m = re.search(r"(\d+)", str(score))
        #             score = int(m.group(1)) if m else 10
        #         except Exception:
        #             score = 10
        # except Exception:
        #     score = 10
        #
        # if score < 7:
        #     try:
        #         refined = await self.reviewer.refine({"summary": summary_text})
        #         summary_text = refined.get("summary", summary_text)
        #     except Exception:
        #         pass

        # store emails in longer-term memory
        try:
            records = self._ensure_ids(messages)
            store_email_memory(records)
        except Exception as e:
            logger.error("Failed to store emails in memory: %s", e)

        logger.info("Initial summary result → %s", summary_text)
        return {"summary": summary_text}

    # -------------------------------------------------------------------------
    # FOLLOW-UP — plan decided by model; supports single/sequential/parallel
    # -------------------------------------------------------------------------
    async def follow_up(
        self,
        messages: List[Any],
        query: str,
        sender_email: Optional[str] = None,
        mode: str = "sequential",
    ) -> Dict[str, Any]:
        """Follow-up: plan is decided by LLM. Loads active emails from DB if messages empty."""
        user_language = detect_language(query, messages)
        session_id = sender_email or "default"

        # Load active messages from DB if none provided
        try:
            active_messages = messages or load_active_emails(session_id)
        except Exception as e:
            logger.error("Failed to load active emails: %s", e)
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

        # Ensure messages are serializable dicts and have ids
        active_messages = self._ensure_ids(active_messages)

        # Decide plan
        plan = await self._decide_plan(query, user_language=user_language)
        logger.info("Follow-up execution plan → %s", plan)

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

        # Truncate plan to protect quota
        if len(plan) > self.max_tools:
            logger.info(
                "Truncating plan from %d to %d tools to protect quota", len(plan), self.max_tools
            )
            plan = plan[: self.max_tools]

        executor = PlanExecutor(
            filter_tool=self.filter_tool,
            newsletter_tool=self.newsletter_tool,
            content_tool=self.content_tool,
            key_points_tool=self.key_points_tool,
            auto_reply_tool=self.auto_reply_tool,
            deadline_tool=self.deadline_tool,
            capabilities_tip=self.capabilities_tip,
        )

        # Execute plan according to mode
        results: List[Dict[str, Any]] = []

        if mode == "single":
            tool = plan[0]
            try:
                res = await executor.run_plan(
                    active_messages, [tool], query, user_language=user_language
                )
            except Exception as e:
                logger.exception("Tool %s failed in single mode: %s", tool, e)
                res = {}
            results.append(res)

        elif mode == "parallel":

            async def run_one(t):
                try:
                    return await executor.run_plan(
                        active_messages, [t], query, user_language=user_language
                    )
                except Exception as e:
                    logger.exception("Tool %s failed in parallel mode: %s", t, e)
                    return {}

            tasks = [run_one(t) for t in plan]
            results = await asyncio.gather(*tasks)

        else:  # sequential
            for t in plan:
                try:
                    res = await executor.run_plan(
                        active_messages, [t], query, user_language=user_language
                    )
                except Exception as e:
                    logger.exception("Tool %s failed in sequential mode: %s", t, e)
                    res = {}
                results.append(res)

        # Merge results: aggregate + normalize
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

        # Merge logic: summary first non-empty in plan order; lists extend; dicts shallow merge
        for idx, res in enumerate(results):
            if not isinstance(res, dict):
                continue
            # summary
            if not merged["summary"]:
                s = res.get("summary")
                if isinstance(s, str) and s.strip():
                    merged["summary"] = s.strip()
            # lists
            for list_key in ("key_tasks", "deadlines", "key_points", "filter_results", "auto_replies"):
                val = res.get(list_key)
                if isinstance(val, list):
                    merged[list_key].extend(val)
            # newsletter_insights
            ni = res.get("newsletter_insights")
            if isinstance(ni, dict):
                merged["newsletter_insights"].update(ni)
            # messages
            msgs = res.get("messages")
            if isinstance(msgs, list) and msgs:
                merged["messages"].extend(msgs)
            else:
                merged["messages"].append(
                    {
                        "role": "agent",
                        "tool": plan[idx] if idx < len(plan) else "unknown",
                        "content": res.get("summary", ""),
                    }
                )

        # Deduplicate lists by stable key
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

        # Normalize structure
        merged = self._normalize_result(merged)

        # Reviewer: score + refine (DISABLED)
        # try:
        #     score = await self.reviewer.score(merged)
        #     if not isinstance(score, int):
        #         try:
        #             import re
        #             m = re.search(r"(\d+)", str(score))
        #             score = int(m.group(1)) if m else 10
        #         except Exception:
        #             score = 10
        # except Exception:
        #     score = 10
        #
        # if score < 7:
        #     try:
        #         merged = await self.reviewer.refine(merged)
        #     except Exception:
        #         logger.exception("Reviewer refine failed")

        logger.info("Follow-up result → %s", json.dumps(merged, ensure_ascii=False, indent=2))
        return merged

    # -------------------------------------------------------------------------
    # Legacy: analyze_emails (alias to initial_summary)
    # -------------------------------------------------------------------------
    async def analyze_emails(
        self,
        messages: List[Any],
        query: Optional[str],
        sender_email: Optional[str],
    ) -> Dict[str, Any]:
        return await self.initial_summary(
            messages, query=query or "Summarize the selected emails.", sender_email=sender_email
        )