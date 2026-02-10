# server/core/executor.py
import logging
import time
from typing import Any, Dict, List, Sequence

logger = logging.getLogger(__name__)


class PlanExecutor:
    """Executes tools according to plan sequentially, with graceful fallbacks."""

    def __init__(
        self,
        filter_tool,
        newsletter_tool,
        content_tool,
        key_points_tool,
        auto_reply_tool,
        deadline_tool,
        capabilities_tip: str,
    ):
        self.filter_tool = filter_tool
        self.newsletter_tool = newsletter_tool
        self.content_tool = content_tool
        self.key_points_tool = key_points_tool
        self.auto_reply_tool = auto_reply_tool
        self.deadline_tool = deadline_tool
        self.capabilities_tip = capabilities_tip

    async def run_plan(
            self,
            messages: List[Dict[str, Any]],
            plan: Sequence[str],
            query: str,
            user_language: str = "English",
    ) -> Dict[str, Any]:

        response: Dict[str, Any] = {
            "summary": "",
            "key_tasks": [],
            "deadlines": [],
            "filter_results": [],
            "newsletter_insights": {},
            "auto_replies": [],
            "key_points": [],
            "messages": [],
            "capabilities_tip": self.capabilities_tip,
            "raw_model_output": None,
            "executed_tools": [],
        }

        executed_tools: List[str] = []
        filter_result: Dict[str, Any] = {}

        # -----------------------------
        # Helpers
        # -----------------------------
        def _ensure_list(value):
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                return [line.strip() for line in value.splitlines() if line.strip()]
            return [] if value is None else [value]

        def _normalize_filtered_emails(value):
            normalized = []
            if isinstance(value, list):
                for idx, v in enumerate(value):
                    if isinstance(v, dict):
                        body = v.get("body") or v.get("snippet") or ""
                        if isinstance(body, str) and len(body) > 800:
                            body = body[:800] + "…"
                        normalized.append(
                            {
                                "id": v.get("id", str(idx + 1)),
                                "subject": v.get("subject", "") or "",
                                "body": body,
                                "tags": v.get("tags", []) if isinstance(v.get("tags", []), list) else [],
                                "priority": v.get("priority", "low"),
                                "recommended_action": v.get("recommended_action", "ignore"),
                            }
                        )
            elif isinstance(value, str):
                normalized.append(
                    {
                        "id": "1",
                        "subject": "",
                        "body": value[:400],
                        "tags": [],
                        "priority": "low",
                        "recommended_action": "ignore",
                    }
                )
            return normalized

        def _normalize_deadlines(value):
            if not isinstance(value, list):
                return []
            out = []
            for idx, item in enumerate(value):
                if isinstance(item, dict):
                    email_id = item.get("email_id") or item.get("id") or f"deadline_{idx}"
                    deadline = item.get("deadline") or ""
                    description = item.get("description") or item.get("context") or ""
                    out.append(
                        {
                            "email_id": str(email_id),
                            "deadline": str(deadline),
                            "description": str(description),
                        }
                    )
            return out

        def _normalize_key_points(value):
            if not isinstance(value, list):
                return []
            out = []
            for idx, item in enumerate(value):
                if isinstance(item, dict):
                    email_id = item.get("email_id") or item.get("id") or f"email_{idx}"
                    points = item.get("points")
                    pts = _ensure_list(points)
                    out.append({"email_id": str(email_id), "points": pts})
            return out

        # -----------------------------
        # FILTER TOOL
        # -----------------------------
        if "filter" in plan:
            try:
                filter_result = await self.filter_tool.run(messages=messages, user_language=user_language)
                emails_raw = filter_result.get("filter_results") or filter_result.get("emails") or []
                response["filter_results"] = _normalize_filtered_emails(emails_raw)
                response["messages"].append(
                    {"role": "agent", "tool": self.filter_tool.name,
                     "content": filter_result.get("summary", "Filtering complete.")}
                )
                executed_tools.append("filter")
            except Exception as e:
                logger.error("Filter tool failed: %s", e)

        # -----------------------------
        # CONTENT TOOL
        # -----------------------------
        if "content" in plan:
            try:
                content_result = await self.content_tool.run(
                    messages=messages, user_query=query, user_language=user_language
                )
                summary = content_result.get("summary", "")
                if isinstance(summary, str) and summary.strip():
                    response["summary"] = summary.strip()
                response["messages"].append(
                    {"role": "agent", "tool": self.content_tool.name,
                     "content": response["summary"] or "Analysis complete."}
                )
                executed_tools.append("content")
            except Exception as e:
                logger.error("Content tool failed: %s", e)

        # -----------------------------
        # OTHER TOOLS
        # -----------------------------
        for tool_name in plan:
            if tool_name in ("filter", "content"):
                continue
            try:
                if tool_name == "key_points":
                    key_points_result = await self.key_points_tool.run(
                        messages=messages, user_query=query, user_language=user_language
                    )
                    executed_tools.append("key_points")
                    kp = key_points_result.get("key_points", []) if isinstance(key_points_result, dict) else []
                    response["key_points"].extend(_normalize_key_points(kp))
                    kt = key_points_result.get("key_tasks", []) if isinstance(key_points_result, dict) else []
                    for item in kt:
                        if isinstance(item, dict):
                            eid = item.get("email_id") or item.get("id")
                            task = item.get("task")
                            if eid and task:
                                response["key_tasks"].append({"email_id": str(eid), "task": str(task)})
                    response["messages"].append(
                        {"role": "agent", "tool": self.key_points_tool.name,
                         "content": "Key points and tasks extracted."}
                    )

                elif tool_name == "deadlines":
                    deadlines_result = await self.deadline_tool.run(
                        messages=messages, user_query=query, user_language=user_language
                    )
                    executed_tools.append("deadlines")
                    dl = deadlines_result.get("deadlines", []) if isinstance(deadlines_result, dict) else []
                    response["deadlines"].extend(_normalize_deadlines(dl))
                    summary = deadlines_result.get("summary") if isinstance(deadlines_result, dict) else ""
                    response["messages"].append(
                        {"role": "agent", "tool": self.deadline_tool.name,
                         "content": summary or "Deadlines extracted."}
                    )

                elif tool_name == "newsletter":
                    newsletter_result = await self.newsletter_tool.run(
                        messages=messages, filter_data=filter_result,
                        weekly_metrics={}, user_language=user_language
                    )
                    executed_tools.append("newsletter")
                    response["newsletter_insights"] = newsletter_result or {}
                    digest_text = newsletter_result.get("digest") if isinstance(newsletter_result, dict) else ""
                    response["messages"].append(
                        {"role": "agent", "tool": self.newsletter_tool.name,
                         "content": digest_text or "Digest prepared."}
                    )

                elif tool_name == "auto":
                    auto_reply_result = await self.auto_reply_tool.run(
                        messages=messages, filter_data=filter_result, user_language=user_language
                    )
                    executed_tools.append("auto")
                    templates = auto_reply_result.get("auto_replies", []) if isinstance(auto_reply_result, dict) else []
                    normalized_templates = []
                    for idx, t in enumerate(templates):
                        if isinstance(t, dict):
                            tid = t.get("id") or idx + 1
                            text = t.get("template") or t.get("text") or ""
                        else:
                            tid = idx + 1
                            text = str(t)
                        normalized_templates.append({"id": tid, "template": str(text)})
                    response["auto_replies"] = normalized_templates
                    response["messages"].append(
                        {"role": "agent", "tool": self.auto_reply_tool.name,
                         "content": f"Prepared {len(response['auto_replies'])} auto-replies."}
                    )

            except Exception as e:
                logger.error("Tool %s failed: %s", tool_name, e)
                response["messages"].append(
                    {"role": "agent", "tool": tool_name,
                     "content": f"Sorry, the {tool_name} tool could not process the emails."}
                )

        # -----------------------------
        # FINALIZATION
        # -----------------------------
        if not response["messages"] and response["summary"]:
            response["messages"].append({"role": "agent", "tool": "summary", "content": response["summary"]})
        if not response["summary"] and response["messages"]:
            response["summary"] = response["messages"][-1]["content"]

        # Dedup executed tools
        seen = set()
        executed_unique = []
        for t in executed_tools:
            if t not in seen:
                seen.add(t)
                executed_unique.append(t)
        response["executed_tools"] = executed_unique

        return response

