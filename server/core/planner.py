# server/core/plan_builder.py
import logging
from typing import List
from langchain.prompts import PromptTemplate

logger = logging.getLogger(__name__)


class PlanBuilder:
    """Decides which tools to run based on query"""

    async def build_plan(self, query: str, llm) -> List[str]:
        lowered = (query or "").lower()
        plan: List[str] = []

        # --- Heuristic: explicit reply intent ---
        if any(word in lowered for word in ["ответить", "ответ", "reply", "respond"]):
            plan = ["content", "auto"]
            logger.info("PlanBuilder heuristic triggered: %s", plan)

        # --- Heuristic: explicit key points intent (high priority) ---
        elif any(
            word in lowered
            for word in [
                "ключевые пункты",
                "ключевые моменты",
                "key points",
                "важное",
                "главное",
                "summary points",
                "bullet points",
                "основные пункты",
            ]
        ):
            plan = ["key_points"]
            logger.info("PlanBuilder key_points heuristic triggered: %s", plan)

        else:
            # --- LLM-based planner (fallback when heuristics don't match) ---
            prompt = PromptTemplate.from_template(
                """
You are a planner for the mail agent.
Available tools: filter, newsletter, content, auto, key_points, deadlines.

Task: decide which tools to run and in what order based on the user query.
Return ONLY a CSV string with tool names in execution order.

User query: "{query}"

Format example: filter,content,key_points
"""
            )
            formatted = prompt.format(query=query)
            logger.debug("PlanBuilder prompt:\n%s", formatted)

            try:
                raw = await llm.ainvoke(formatted)
                logger.debug("PlanBuilder raw LLM response: %r", raw)

                plan_text = getattr(raw, "content", str(raw)).strip()
                logger.debug("PlanBuilder extracted plan text: %s", plan_text)

                plan = [p.strip() for p in plan_text.split(",") if p.strip()]
            except Exception as e:
                logger.error("PlanBuilder LLM call failed: %s", e)
                plan = []

        # --- Fallback to safe default ---
        if not plan:
            plan = ["content"]
            logger.info("PlanBuilder fallback to default plan: %s", plan)

        # --- Dependencies: ensure filter runs before newsletter/auto if present ---
        if "newsletter" in plan and "filter" not in plan:
            plan.insert(0, "filter")
        if "auto" in plan and "filter" not in plan:
            plan.insert(0, "filter")

        # --- Allowed tools set ---
        allowed = {"filter", "newsletter", "content", "auto", "key_points", "deadlines"}
        plan = [t for t in plan if t in allowed]

        logger.info("PlanBuilder final execution plan: %s", plan)
        return plan
