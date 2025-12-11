# server/metrics/prometheus_metrics.py
from prometheus_client import Counter, Histogram

# Labels: tool name and status (success/error/timeout)
LLM_CALLS = Counter("llm_calls_total", "Total LLM calls", ["tool", "status"])
LLM_LATENCY = Histogram("llm_call_duration_seconds", "LLM call latency seconds", ["tool"])

def record_call(tool: str, status: str, duration: float | None = None) -> None:
    """Record a call with status and optional duration."""
    try:
        LLM_CALLS.labels(tool=tool, status=status).inc()
        if duration is not None:
            LLM_LATENCY.labels(tool=tool).observe(duration)
    except Exception:
        # metrics should not break the app
        pass
