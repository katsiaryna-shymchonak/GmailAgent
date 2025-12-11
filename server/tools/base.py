# server/tools/base.py
import asyncio
import logging
import json
import time
from typing import Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from ..config.settings import get_settings
from ..metrics.llm_counters import incr_call, log_snapshot
from ..metrics.prometheus_metrics import record_call

logger = logging.getLogger(__name__)
settings = get_settings()


class BaseTool:
    """Base class for all tools: robust LLM invocation, strict JSON parsing,
    and LLM call metrics (in-process + Prometheus)."""

    def __init__(self, schema: Dict[str, Any], tool_name: str = "generic"):
        self.schema = schema
        self.tool_name = tool_name

        self.model = ChatGoogleGenerativeAI(
            google_api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            temperature=0.3,
            max_retries=2,
        )

        self.timeout = 120

    async def _invoke(self, prompt: str) -> Any:
        """Invoke the underlying model in a way compatible with multiple client versions.
        Records metrics and latency. Returns raw response object or empty string on failure.
        """
        start = time.monotonic()
        await incr_call(self.tool_name, success=None)  # mark started

        try:
            # Try keyword 'input' first
            try:
                raw = await asyncio.wait_for(self.model.ainvoke(input=prompt), timeout=self.timeout)
            except TypeError:
                # Try positional string
                try:
                    raw = await asyncio.wait_for(self.model.ainvoke(prompt), timeout=self.timeout)
                except TypeError:
                    # Try agenerate-style (langchain-like)
                    raw = await asyncio.wait_for(
                        self.model.agenerate(messages=[[{"role": "user", "content": prompt}]]),
                        timeout=self.timeout,
                    )
            duration = time.monotonic() - start
            # success metrics
            await incr_call(self.tool_name, success=True)
            record_call(self.tool_name, "success", duration)
            logger.debug("LLM call success tool=%s duration=%.3f", self.tool_name, duration)
            return raw
        except asyncio.TimeoutError:
            duration = time.monotonic() - start
            await incr_call(self.tool_name, success=False)
            record_call(self.tool_name, "timeout", duration)
            logger.error("LLM call timed out after %s seconds (tool=%s)", self.timeout, self.tool_name)
            return ""
        except Exception as e:
            duration = time.monotonic() - start
            await incr_call(self.tool_name, success=False)
            # classify resource/quota errors as 'rate_limited' if message contains 429/ResourceExhausted
            status = "error"
            msg = str(e).lower()
            if "quota" in msg or "resourceexhausted" in msg or "429" in msg:
                status = "rate_limited"
            record_call(self.tool_name, status, duration)
            logger.error("LLM call failed (tool=%s): %s", self.tool_name, e)
            return ""

    def _extract_text(self, raw: Any) -> str:
        """Robust extraction of text content from various raw response shapes."""
        if raw is None:
            return ""
        if isinstance(raw, str):
            return raw

        if hasattr(raw, "content"):
            try:
                return getattr(raw, "content") or ""
            except Exception:
                pass
        if hasattr(raw, "text"):
            try:
                return getattr(raw, "text") or ""
            except Exception:
                pass

        try:
            gens = getattr(raw, "generations", None)
            if gens and isinstance(gens, list) and len(gens) > 0:
                first = gens[0]
                if isinstance(first, list) and len(first) > 0 and hasattr(first[0], "text"):
                    return first[0].text or ""
                if hasattr(first, "text"):
                    return getattr(first, "text") or ""
        except Exception:
            pass

        try:
            if isinstance(raw, dict):
                for k in ("content", "text", "message", "output"):
                    if k in raw and isinstance(raw[k], str):
                        return raw[k]
                return json.dumps(raw, ensure_ascii=False)
        except Exception:
            pass

        try:
            return str(raw)
        except Exception:
            return ""

    async def call(
        self,
        prompt: str,
        variables: Dict[str, Any] = None,
        user_language: str = "English"
    ) -> Dict[str, Any]:
        """Call the model, parse JSON strictly, and return a dict matching the schema."""
        variables = variables or {}
        text = ""

        try:
            raw = await self._invoke(prompt)
            if not raw:
                raise ValueError("Empty response from LLM")

            text = self._extract_text(raw)
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
                logger.warning("LLM returned non-JSON, wrapping into summary (tool=%s)", self.tool_name)
                if "summary" in self.schema:
                    fallback = {k: ([] if isinstance(v, list) else ({} if isinstance(v, dict) else "")) for k, v in self.schema.items()}
                    fallback["summary"] = cleaned
                    logger.debug("BaseTool FILTERED RESULT keys=%s", list(fallback.keys()))
                    return fallback
                return {"summary": cleaned}

            if not isinstance(result, dict):
                raise ValueError("Invalid JSON structure: expected object at top level")

            allowed = set(self.schema.keys())
            filtered = {k: v for k, v in result.items() if k in allowed}

            for key, val in self.schema.items():
                if key not in filtered:
                    if isinstance(val, list):
                        filtered[key] = []
                    elif isinstance(val, dict):
                        filtered[key] = {}
                    else:
                        filtered[key] = ""

            logger.debug("BaseTool FILTERED RESULT keys=%s", list(filtered.keys()))
            return filtered

        except Exception as e:
            logger.warning("Structured parse failed (tool=%s): %s", self.tool_name, e)
            fallback = {}
            for key, val in self.schema.items():
                if isinstance(val, list):
                    fallback[key] = []
                elif isinstance(val, dict):
                    fallback[key] = {}
                else:
                    if key in ("summary", "weekly_report") and text:
                        fallback[key] = str(text).strip()
                    else:
                        fallback[key] = (
                            "Service overloaded, please retry later."
                            if not user_language.lower().startswith("rus")
                            else "Сервис перегружен, попробуйте позже."
                        )
            return fallback
