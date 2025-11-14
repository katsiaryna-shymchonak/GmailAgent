from __future__ import annotations

import json
import textwrap
from typing import Any, Dict, Iterable, List, Sequence

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from .config import get_settings
from .database import fetch_recent_emails, get_weekly_metrics, store_email_memory

settings = get_settings()
CAPABILITIES_TIP = (
    "Агент умеет: фильтровать письма, управлять рассылками, находить задачи и дедлайны, "
    "готовить автоответы и недельные отчёты."
)


def _format_messages(messages: Iterable[Dict[str, Any]]) -> str:
    sections = []
    for idx, message in enumerate(messages, start=1):
        sections.append(
            textwrap.dedent(
                f"""
                Email {idx}:
                ID: {message.get('id')}
                From: {message.get('from') or message.get('from_') or message.get('sender_email')}
                Subject: {message.get('subject')}
                Snippet: {message.get('snippet')}
                Body:
                {message.get('body') or message.get('content') or message.get('snippet')}
                """
            ).strip()
        )
    return "\n\n".join(sections) if sections else "Нет содержимого."


class BaseTool:
    name = "base"

    def __init__(self) -> None:
        self.model = genai.GenerativeModel(settings.gemini_model)

    def _call_model(self, prompt: str, temperature: float = 0.2) -> Dict[str, Any]:
        response = self.model.generate_content(
            prompt,
            generation_config=GenerationConfig(
                temperature=temperature,
                response_mime_type="application/json",
            ),
        )
        text = getattr(response, "text", None)
        if isinstance(text, list):
            text = text[0]
        if not isinstance(text, str) or not text:
            text = str(response)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}


class FilteringTool(BaseTool):
    name = "Фильтрация и приоритизация"

    def run(self, *, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt = textwrap.dedent(
            f"""
            Ты помощник по почте. Для каждого письма определи тип (meeting | newsletter | personal | work),
            приоритет (high | normal | low), нужно ли отвечать, какие теги добавить (Meetings, Newsletters, Action Required),
            и какие действия выполнить (например, добавить встречу в календарь).

            Верни JSON:
            {{
              "emails": [
                {{
                  "id": "...",
                  "type": "...",
                  "priority": "...",
                  "requires_reply": true/false,
                  "tags": ["...", ...],
                  "actions": ["...", ...],
                  "notes": "краткое пояснение"
                }}
              ],
              "summary": "краткое описание",
              "high_priority_ids": ["...", ...]
            }}

            Письма:
            {_format_messages(messages)}
            """
        ).strip()
        return self._call_model(prompt)


class NewsletterTool(BaseTool):
    name = "Умное управление рассылками"

    def run(
        self,
        *,
        messages: List[Dict[str, Any]],
        filter_data: Dict[str, Any],
        weekly_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        prompt = textwrap.dedent(
            f"""
            Ты помогаешь управлять рассылками.
            На основе данных о письмах и еженедельных метрик предложи:
              - от каких рассылок отписаться,
              - какие оставить,
              - сформируй digest (краткий обзор),
              - сделай недельный отчёт по статистике (кол-во писем, митингов, рассылок, % requiring reply vs информационных).

            Обязательно JSON:
            {{
              "unsubscribe": ["..."],
              "keep": ["..."],
              "digest": "...",
              "weekly_report": "...",
              "metrics_used": {{...}}
            }}

            Классификация писем: {json.dumps(filter_data.get('emails', []), ensure_ascii=False)}

            Метрики за неделю: {json.dumps(weekly_metrics, default=str, ensure_ascii=False)}
            """
        ).strip()
        return self._call_model(prompt, temperature=0.1)


class ContentAnalysisTool(BaseTool):
    name = "Анализ содержания писем"

    def run(self, *, messages: List[Dict[str, Any]], user_query: str) -> Dict[str, Any]:
        prompt = textwrap.dedent(
            f"""
            Ты анализируешь письма.
            Извлеки ключевые задачи/дедлайны, сделай summary и draft-ответ (пример: «Спасибо, отчёт будет готов к четвергу»).
            Формат JSON:
            {{
              "summary": "...",
              "key_tasks": ["..."],
              "deadlines": ["..."],
              "draft_reply": "...",
              "raw": "опционально"
            }}

            Запрос пользователя: {user_query or "Сформируй резюме писем."}

            Письма:
            {_format_messages(messages)}
            """
        ).strip()
        return self._call_model(prompt)


class AutoReplyTool(BaseTool):
    name = "Персонализированные автоответы"

    def run(self, *, messages: List[Dict[str, Any]], filter_data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = textwrap.dedent(
            f"""
            Создай персонализированные шаблоны автоответов для типовых писем.
            Используй примеры:
              - «Спасибо за информацию»
              - «Принято, добавлю в план»
              - «Неактуально для меня, но спасибо»

            Верни JSON:
            {{
              "templates": [
                {{
                  "id": "...",
                  "subject": "...",
                  "type": "meeting/newsletter/...",
                  "template": "...",
                  "notes": "когда использовать"
                }}
              ],
              "general_templates": ["...", ...]
            }}

            Классификация писем: {json.dumps(filter_data.get('emails', []), ensure_ascii=False)}
            """
        ).strip()
        return self._call_model(prompt, temperature=0.3)


class AgentOrchestrator:
    def __init__(self) -> None:
        self.filter_tool = FilteringTool()
        self.newsletter_tool = NewsletterTool()
        self.content_tool = ContentAnalysisTool()
        self.auto_reply_tool = AutoReplyTool()
        self.capabilities_tip = CAPABILITIES_TIP

    def analyze_emails(self, payload_messages: List[Any], query: str, sender_email: str | None) -> Dict[str, Any]:
        tool_messages = [
            msg if isinstance(msg, dict) else msg.dict(by_alias=True)  # type: ignore[union-attr]
            for msg in payload_messages
        ]
        effective_messages = tool_messages or fetch_recent_emails()
        plan = self._plan_tools(query, bool(tool_messages))
        result = self._run_plan(effective_messages, plan, query or "")
        if tool_messages and result.get("filter_results"):
            self._persist_memory(tool_messages, {"emails": result["filter_results"]})
        result["capabilities_tip"] = self.capabilities_tip
        return result

    def weekly_summary(self, query: str, messages: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        # Use provided messages from Gmail API, or fall back to database
        if messages:
            # Convert EmailMessage objects to dict format if needed
            formatted_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    formatted_messages.append({
                        "id": msg.get("id", ""),
                        "subject": msg.get("subject", ""),
                        "snippet": msg.get("snippet", ""),
                        "from": msg.get("from") or msg.get("from_", ""),
                        "body": msg.get("body", msg.get("snippet", "")),
                    })
                else:
                    # Pydantic model
                    formatted_messages.append({
                        "id": getattr(msg, "id", ""),
                        "subject": getattr(msg, "subject", ""),
                        "snippet": getattr(msg, "snippet", ""),
                        "from": getattr(msg, "from_", "") or getattr(msg, "from", ""),
                        "body": getattr(msg, "body", getattr(msg, "snippet", "")),
                    })
            messages_to_use = formatted_messages
        else:
            # Fallback to database if no messages provided
            messages_to_use = fetch_recent_emails()
        
        if not messages_to_use:
            return {
                "summary": "Нет писем за неделю.",
                "messages": [
                    {"role": "agent", "tool": "weekly", "content": "Не найдено писем за последние 7 дней."}
                ],
                "capabilities_tip": self.capabilities_tip,
            }
        
        plan = self._plan_tools(query or "Недельный отчёт", has_selected=bool(messages))
        result = self._run_plan(messages_to_use, plan, query or "Недельный отчёт")
        result["capabilities_tip"] = self.capabilities_tip
        return result

    def _plan_tools(self, query: str, has_selected: bool) -> List[str]:
        q = (query or "").lower()
        plan: List[str] = []
        def add(tool: str):
            if tool not in plan:
                plan.append(tool)

        keywords = {
            "meeting": "filter",
            "митинг": "filter",
            "созв": "filter",
            "tag": "filter",
            "filter": "filter",
            "рассыл": "newsletter",
            "digest": "newsletter",
            "недель": "newsletter",
            "summary": "content",
            "резюме": "content",
            "задач": "content",
            "deadline": "content",
            "дедлай": "content",
            "ответ": "auto",
            "auto": "auto",
            "шаблон": "auto",
        }
        for key, tool in keywords.items():
            if key in q:
                add(tool)
        if not plan:
            add("content")
        if "newsletter" in plan and "filter" not in plan:
            plan.insert(0, "filter")
        if "auto" in plan and "filter" not in plan:
            plan.insert(0, "filter")
        if not has_selected:
            if "newsletter" not in plan:
                plan.append("newsletter")
        return plan

    def _run_plan(self, messages: List[Dict[str, Any]], plan: Sequence[str], query: str) -> Dict[str, Any]:
        response = {
            "summary": "",
            "key_tasks": [],
            "deadlines": [],
            "draft_reply": "",
            "filter_results": [],
            "newsletter_insights": {},
            "auto_replies": [],
            "weekly_report": "",
            "messages": [],
        }
        filter_result = {}
        newsletter_result = {}
        for tool_name in plan:
            if tool_name == "filter":
                filter_result = self.filter_tool.run(messages=messages)
                response["filter_results"] = filter_result.get("emails", [])
                response["messages"].append(
                    {"role": "agent", "tool": self.filter_tool.name, "content": filter_result.get("summary", "Фильтрация выполнена.")}
                )
            elif tool_name == "newsletter":
                if not filter_result:
                    filter_result = self.filter_tool.run(messages=messages)
                    response["filter_results"] = filter_result.get("emails", [])
                newsletter_result = self.newsletter_tool.run(
                    messages=messages,
                    filter_data=filter_result,
                    weekly_metrics=get_weekly_metrics(),
                )
                response["newsletter_insights"] = newsletter_result
                response["weekly_report"] = newsletter_result.get("weekly_report", "")
                digest_text = newsletter_result.get("digest") or newsletter_result.get("weekly_report") or "Digest сформирован."
                response["messages"].append(
                    {"role": "agent", "tool": self.newsletter_tool.name, "content": digest_text}
                )
            elif tool_name == "auto":
                if not filter_result:
                    filter_result = self.filter_tool.run(messages=messages)
                    response["filter_results"] = filter_result.get("emails", [])
                auto_reply_result = self.auto_reply_tool.run(messages=messages, filter_data=filter_result)
                response["auto_replies"] = auto_reply_result.get("templates", [])
                summary = f"Подготовлено {len(response['auto_replies'])} шаблонов автоответов."
                response["messages"].append({"role": "agent", "tool": self.auto_reply_tool.name, "content": summary})
            elif tool_name == "content":
                content_result = self.content_tool.run(messages=messages, user_query=query)
                response["summary"] = content_result.get("summary") or response["summary"]
                response["key_tasks"] = content_result.get("key_tasks", [])
                response["deadlines"] = content_result.get("deadlines", [])
                response["draft_reply"] = content_result.get("draft_reply", "")
                response["messages"].append(
                    {"role": "agent", "tool": self.content_tool.name, "content": response["summary"] or "Анализ завершён."}
                )
        if not response["messages"] and response["summary"]:
            response["messages"].append({"role": "agent", "tool": "summary", "content": response["summary"]})
        if not response["summary"] and response["messages"]:
            response["summary"] = response["messages"][-1]["content"]
        return response

    def _persist_memory(self, messages: List[Dict[str, Any]], filter_result: Dict[str, Any]) -> None:
        email_map = {msg.get("id"): msg for msg in messages if msg.get("id")}
        records = []
        for item in filter_result.get("emails", []):
            msg = email_map.get(item.get("id"))
            if not msg:
                continue
            records.append(
                {
                    "id": item.get("id"),
                    "sender_email": msg.get("from") or msg.get("from_"),
                    "subject": msg.get("subject"),
                    "snippet": msg.get("snippet"),
                    "body": msg.get("body"),
                    "email_type": item.get("type"),
                    "priority": item.get("priority"),
                    "requires_reply": item.get("requires_reply"),
                    "tags": item.get("tags"),
                    "metadata": item,
                }
            )
        if records:
            store_email_memory(records)

