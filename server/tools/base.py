# server/tools/base.py
import asyncio
import logging
import json
import time
from typing import Dict, Any

# Requires: pip install langchain-groq
from langchain_groq import ChatGroq
from ..config.settings import get_settings
from ..metrics.llm_counters import incr_call, log_snapshot
from ..metrics.prometheus_metrics import record_call

logger = logging.getLogger(__name__)
settings = get_settings()


class BaseTool:
    """Base class for all tools: robust LLM invocation via Groq, strict JSON parsing,
    and LLM call metrics (in-process + Prometheus)."""

    def __init__(self, schema: Dict[str, Any], tool_name: str = "generic"):
        self.schema = schema
        self.tool_name = tool_name

        # Initializing ChatGroq
        self.model = ChatGroq(
            groq_api_key=settings.groq_api_key,
            model_name=settings.groq_model,
            temperature=0.3,
            max_retries=2
        )

        self.timeout = 120

    async def _invoke(self, prompt: str) -> Any:
        """Invoke the underlying model in a way compatible with multiple client versions.
        Records metrics and latency. Returns raw response object or empty string on failure.
        """
        start = time.monotonic()
        await incr_call(self.tool_name, success=None)  # mark started

        try:
            # Groq/LangChain invocation
            try:
                # Try standard invocation
                raw = await asyncio.wait_for(self.model.ainvoke(prompt), timeout=self.timeout)
            except TypeError:
                # Fallback for older interface versions
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
            # classify resource/quota errors
            status = "error"
            msg = str(e).lower()
            if "rate limit" in msg or "429" in msg or "quota" in msg:
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
            # Handle generations list if present
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

            # Clean markdown code blocks often returned by Llama models
            if cleaned.startswith("```"):
                # Remove first line (e.g., ```json) and last line (```)
                lines = cleaned.splitlines()
                if len(lines) >= 2:
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].strip() == "```":
                        lines = lines[:-1]
                    cleaned = "\n".join(lines).strip()
                else:
                    cleaned = cleaned.strip("`")  # Fallback for single line code blocks

            try:
                result = json.loads(cleaned)
            except json.JSONDecodeError:
                logger.warning("LLM returned non-JSON, wrapping into summary (tool=%s)", self.tool_name)
                # Attempt to find JSON substring if mixed with text
                start_idx = cleaned.find('{')
                end_idx = cleaned.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    try:
                        possible_json = cleaned[start_idx:end_idx + 1]
                        result = json.loads(possible_json)
                    except json.JSONDecodeError:
                        if "summary" in self.schema:
                            fallback = {k: ([] if isinstance(v, list) else ({} if isinstance(v, dict) else "")) for k, v
                                        in self.schema.items()}
                            fallback["summary"] = cleaned
                            return fallback
                        return {"summary": cleaned}
                else:
                    if "summary" in self.schema:
                        fallback = {k: ([] if isinstance(v, list) else ({} if isinstance(v, dict) else "")) for k, v in
                                    self.schema.items()}
                        fallback["summary"] = cleaned
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