# server/metrics/llm_counters.py
import asyncio
import logging
from collections import defaultdict
from typing import Dict

logger = logging.getLogger(__name__)

# Простые глобальные счётчики
_total_calls: int = 0
_success_calls: int = 0
_failed_calls: int = 0
_per_tool: Dict[str, int] = defaultdict(int)
_per_tool_success: Dict[str, int] = defaultdict(int)
_per_tool_failed: Dict[str, int] = defaultdict(int)

_lock = asyncio.Lock()


async def incr_call(tool_name: str, success: bool | None = None) -> None:
    """Increment counters. success: True/False/None (None = started)."""
    global _total_calls, _success_calls, _failed_calls
    async with _lock:
        _total_calls += 1
        _per_tool[tool_name] += 1
        if success is True:
            _success_calls += 1
            _per_tool_success[tool_name] += 1
        elif success is False:
            _failed_calls += 1
            _per_tool_failed[tool_name] += 1


def snapshot() -> Dict:
    """Return current counters snapshot (non-blocking)."""
    return {
        "total": _total_calls,
        "success": _success_calls,
        "failed": _failed_calls,
        "per_tool": dict(_per_tool),
        "per_tool_success": dict(_per_tool_success),
        "per_tool_failed": dict(_per_tool_failed),
    }


def log_snapshot(level=logging.INFO) -> None:
    s = snapshot()
    logger.log(
        level,
        "LLM metrics snapshot: total=%d success=%d failed=%d per_tool=%s",
        s["total"],
        s["success"],
        s["failed"],
        s["per_tool"],
    )
