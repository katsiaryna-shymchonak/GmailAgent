import asyncio
import logging
import json
from typing import Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from ..config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class BaseTool:
    """Base class for all tools: manages LLM calls and fallback."""

    def __init__(self, schema: Dict[str, Any]):
        self.schema = schema
        self.model = ChatGoogleGenerativeAI(
            google_api_key=settings.gemini_api_key,
            model=settings.gemini_model,   # убедись, что указано "models/gemini-2.5-flash"
            temperature=0.5,
            max_retries=2,
        )
        self.timeout = 120  # увеличенное время ожидания ответа

    async def _invoke(self, prompt: str) -> Any:
        """Асинхронный вызов модели с таймаутом."""
        try:
            return await asyncio.wait_for(self.model.ainvoke(prompt), timeout=self.timeout)
        except asyncio.TimeoutError:
            logger.error("LLM call timed out after %s seconds", self.timeout)
            return ""
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return ""

    async def call(
        self,
        prompt: str,
        variables: Dict[str, Any],
        user_language: str = "English"
    ) -> Dict[str, Any]:
        """Model call with robust parsing and fallback to valid JSON."""
        text = ""
        try:
            raw = await self._invoke(prompt)
            if not raw:
                raise ValueError("Empty response from LLM")

            text = getattr(raw, "content", raw)
            if not text or not str(text).strip():
                raise ValueError("Empty response from LLM")

            cleaned = str(text).strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`")
                if cleaned.lower().startswith("json"):
                    cleaned = cleaned[4:].strip()

            try:
                result = json.loads(cleaned)
            except json.JSONDecodeError:
                logger.warning("LLM returned non-JSON, wrapping into summary")
                result = {"summary": cleaned}

            # Дополнительная нормализация
            if "emails_summary" in result and isinstance(result["emails_summary"], str):
                try:
                    result["emails_summary"] = json.loads(result["emails_summary"])
                except Exception:
                    pass

            if "emails_summary" in result and isinstance(result["emails_summary"], list):
                tasks, deadlines, replies = [], [], {}
                for email in result["emails_summary"]:
                    if isinstance(email, dict):
                        if "tasks" in email:
                            tasks.extend(email["tasks"])
                        if "deadline" in email:
                            deadlines.append(email["deadline"])
                        if "draft_reply" in email:
                            replies[email.get("id", str(len(replies) + 1))] = email["draft_reply"]
                if tasks:
                    result["key_tasks"] = tasks
                if deadlines:
                    result["deadlines"] = deadlines
                if replies:
                    result["draft_reply"] = replies

            if not isinstance(result, dict):
                raise ValueError("Invalid JSON structure")
            return result

        except Exception as e:
            logger.warning("Structured parse failed: %s", e)
            fallback = {}
            for key, val in self.schema.items():
                if isinstance(val, list):
                    fallback[key] = []
                elif isinstance(val, dict):
                    fallback[key] = {}
                else:
                    fallback[key] = (
                        str(text).strip()
                        if key in ("summary", "weekly_report") and text
                        else (
                            "Service overloaded, please retry later."
                            if not user_language.lower().startswith("rus")
                            else "Сервис перегружен, попробуйте позже."
                        )
                    )
            if "messages" in self.schema:
                fallback["messages"] = [{"role": "agent", "content": str(text) if text else ""}]

            return fallback
