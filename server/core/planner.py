import logging
from typing import List
from langchain.prompts import PromptTemplate

logger = logging.getLogger(__name__)

class PlanBuilder:
    """Decides which tools to run based on query"""

    async def build_plan(self, query: str, llm) -> List[str]:
        lowered = query.lower()
        plan: List[str] = []

        # Эвристика: если явно про "ответить"
        if any(word in lowered for word in ["ответить", "ответ", "reply", "respond"]):
            plan = ["content", "auto"]
            logger.info("PlanBuilder heuristic triggered: %s", plan)
        else:
            prompt = PromptTemplate.from_template(
                """
                You are a planner for the mail agent.
                Tools: filter, newsletter, content, auto.

                Task: decide which tools to run and in what order,
                based on the user query. Return ONLY a CSV string.

                User query: "{query}"

                Format example: filter,content,auto
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

        if not plan:
            plan = ["content"]
            logger.info("PlanBuilder fallback to default plan: %s", plan)

        # Ensure dependencies
        if "newsletter" in plan and "filter" not in plan:
            plan.insert(0, "filter")
        if "auto" in plan and "filter" not in plan:
            plan.insert(0, "filter")

        allowed = {"filter", "newsletter", "content", "auto"}
        plan = [t for t in plan if t in allowed]

        logger.info("PlanBuilder final execution plan: %s", plan)
        return plan
