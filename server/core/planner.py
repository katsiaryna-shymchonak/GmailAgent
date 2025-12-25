# server/core/planner.py
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
                You are a planning module for an email‑analysis agent.

                Your job is to decide which tools to run based on the user query.
                You may choose ONE tool or MULTIPLE tools in a meaningful order.

                Available tools and their purposes:

                1) filter  
                   - Extracts structured metadata from emails (priority, tags, actions).
                   - Should run BEFORE newsletter or auto if they are used.
                   - Use when the user asks to sort, filter, classify, find important/urgent emails.

                2) newsletter  
                   - Analyzes newsletters: digest, unsubscribe suggestions, keep suggestions.
                   - Use when the user asks about newsletters, subscriptions, digests, spammy mailings.

                3) content  
                   - Produces summaries, explanations, overviews, or general analysis.
                   - Use when the user wants a summary, explanation, or general understanding.

                4) auto  
                   - Generates reply drafts or suggested responses.
                   - Use when the user wants to reply, respond, write a message, or draft an email.
                   - Must run AFTER filter if both are used.

                5) key_points  
                   - Extracts key bullet points from emails.
                   - Use when the user asks for key points, main ideas, bullet points, highlights.

                6) deadlines  
                   - Extracts deadlines, due dates, submission times.
                   - Use when the user asks about deadlines, due dates, schedules, or time‑sensitive tasks.

                General rules:
                - You may choose multiple tools if the query requires multiple types of analysis.
                - Order matters: filter → content → key_points → deadlines → auto → newsletter (as needed).
                - If the user asks for several things (e.g., summary + deadlines), include all relevant tools.
                - If the query is ambiguous, choose the minimal reasonable set of tools.
                - Return ONLY a CSV string with tool names in execution order.

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
