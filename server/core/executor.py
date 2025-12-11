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
        capabilities_tip: str
    ):
        self.filter_tool = filter_tool
        self.newsletter_tool = newsletter_tool
        self.content_tool = content_tool
        self.key_points_tool = key_points_tool
        self.auto_reply_tool = auto_reply_tool
        self.capabilities_tip = capabilities_tip

    async def run_plan(
        self,
        messages: List[Dict[str, Any]],
        plan: Sequence[str],
        query: str,
        user_language: str = "English"
    ) -> Dict[str, Any]:

        # ✅ Унифицированный ответ
        response = {
            "summary": "",
            "key_tasks": [],
            "deadlines": [],
            "filter_results": [],
            "newsletter_insights": {},
            "auto_replies": [],
            "key_points": [],
            "messages": [],
            "capabilities_tip": self.capabilities_tip,
        }

        filter_result: Dict[str, Any] = {}

        # -----------------------------
        # Вспомогательные функции
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
                        normalized.append({
                            "id": v.get("id", str(idx + 1)),
                            "subject": v.get("subject", ""),
                            "body": v.get("body", ""),
                            "tags": v.get("tags", []),
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
            elif isinstance(value, str):
                normalized.append({
                    "id": "1",
                    "subject": "",
                    "body": value,
                    "tags": [],
                    "priority": "low",
                    "recommended_action": "ignore",
                })
            return normalized

        # -----------------------------
        # FILTER TOOL
        # -----------------------------
        if "filter" in plan:
            logger.info("Running filter tool")
            start = time.time()
            try:
                filter_result = await self.filter_tool.run(messages=messages, user_language=user_language)
                emails_raw = filter_result.get("filter_results") or filter_result.get("emails") or []
                response["filter_results"] = _normalize_filtered_emails(emails_raw)

                response["messages"].append({
                    "role": "agent",
                    "tool": self.filter_tool.name,
                    "content": filter_result.get("summary", "Filtering complete."),
                })
            except Exception as e:
                logger.error("Filter tool failed: %s", e)
            logger.info("Filter completed in %.2fs", time.time() - start)

        # -----------------------------
        # CONTENT TOOL (summary only)
        # -----------------------------
        if "content" in plan:
            logger.info("Running content tool (summary only)")
            start = time.time()
            try:
                content_result = await self.content_tool.run(
                    messages=messages,
                    user_query=query,
                    user_language=user_language
                )

                # ✅ Теперь content возвращает только summary
                summary = content_result.get("summary", "")
                if isinstance(summary, str) and summary.strip():
                    response["summary"] = summary.strip()

                response["messages"].append({
                    "role": "agent",
                    "tool": self.content_tool.name,
                    "content": response["summary"] or (
                        "Анализ завершён." if user_language.lower().startswith("rus") else "Analysis complete."
                    ),
                })

            except Exception as e:
                logger.error("Content tool failed: %s", e)

            logger.info("Content completed in %.2fs", time.time() - start)

        # -----------------------------
        # OTHER TOOLS
        # -----------------------------
        for tool_name in plan:
            if tool_name in ("filter", "content"):
                continue

            logger.info("Running tool: %s", tool_name)
            start = time.time()

            try:
                # -----------------------------
                # NEWSLETTER TOOL
                # -----------------------------
                if tool_name == "newsletter":
                    if not filter_result:
                        filter_result = await self.filter_tool.run(messages=messages, user_language=user_language)
                        emails_raw = filter_result.get("filter_results") or filter_result.get("emails") or []
                        response["filter_results"] = _normalize_filtered_emails(emails_raw)

                    newsletter_result = await self.newsletter_tool.run(
                        messages=messages,
                        filter_data=filter_result,
                        weekly_metrics={},
                        user_language=user_language,
                    )
                    response["newsletter_insights"] = newsletter_result

                    digest_text = newsletter_result.get("digest") or (
                        "Подготовлен дайджест." if user_language.lower().startswith("rus") else "Digest prepared."
                    )
                    response["messages"].append({
                        "role": "agent",
                        "tool": self.newsletter_tool.name,
                        "content": digest_text,
                    })

                # -----------------------------
                # AUTO REPLY TOOL
                # -----------------------------
                elif tool_name == "auto":
                    if not filter_result:
                        filter_result = await self.filter_tool.run(messages=messages, user_language=user_language)
                        emails_raw = filter_result.get("filter_results") or filter_result.get("emails") or []
                        response["filter_results"] = _normalize_filtered_emails(emails_raw)

                    auto_reply_result = await self.auto_reply_tool.run(
                        messages=messages,
                        filter_data=filter_result,
                        user_language=user_language,
                    )

                    templates = auto_reply_result.get("auto_replies", [])
                    if isinstance(templates, str):
                        templates = [templates]
                    elif not isinstance(templates, list):
                        templates = [str(templates)]

                    response["auto_replies"] = [
                        {"id": idx + 1, "template": str(v)}
                        for idx, v in enumerate(templates)
                    ]

                    summary = (
                        f"Подготовлено {len(response['auto_replies'])} автоответов."
                        if user_language.lower().startswith("rus")
                        else f"Prepared {len(response['auto_replies'])} auto-replies."
                    )
                    response["messages"].append({
                        "role": "agent",
                        "tool": self.auto_reply_tool.name,
                        "content": summary,
                    })

                # -----------------------------
                # KEY POINTS TOOL
                # -----------------------------
                elif tool_name == "key_points":
                    key_points_result = await self.key_points_tool.run(
                        messages=messages,
                        user_query=query,
                        user_language=user_language,
                    )

                    kp = key_points_result.get("key_points", [])
                    if isinstance(kp, list):
                        response["key_points"].extend(kp)

                    response["messages"].append({
                        "role": "agent",
                        "tool": self.key_points_tool.name,
                        "content": (
                            "Ключевые пункты извлечены."
                            if user_language.lower().startswith("rus")
                            else "Key points extracted."
                        ),
                    })

                logger.info("Tool %s completed in %.2fs", tool_name, time.time() - start)

            except Exception as e:
                logger.error("Tool %s failed: %s", tool_name, e)
                fallback_msg = (
                    f"Извините, инструмент {tool_name} не смог обработать письма."
                    if user_language.lower().startswith("rus")
                    else f"Sorry, the {tool_name} tool could not process the emails."
                )
                response["messages"].append({
                    "role": "agent",
                    "tool": tool_name,
                    "content": fallback_msg,
                })

        # -----------------------------
        # FINALIZATION
        # -----------------------------
        if not response["messages"] and response["summary"]:
            response["messages"].append({
                "role": "agent",
                "tool": "summary",
                "content": response["summary"],
            })

        if not response["summary"] and response["messages"]:
            response["summary"] = response["messages"][-1]["content"]

        return response
