# server/core/planner.py
import logging
from typing import List
from langchain.prompts import PromptTemplate
from ..tools.base import BaseTool

logger = logging.getLogger(__name__)


class PlanBuilder:
    """
    LLM-driven planner, использующий BaseTool как LLM-обёртку.
    Модель возвращает JSON {"plan": ["tool_name", ...]}.
    """

    def __init__(self) -> None:
        # Специальный "инструмент-планировщик" с простейшей схемой
        self.llm = BaseTool(schema={"plan": ["string"]}, tool_name="planner")

        # Промпт: строго JSON, без CSV, без вольностей
        self.prompt_tmpl = PromptTemplate.from_template(
            """
            You are a planning module for an email-analysis agent.

            Your job is to decide which tools to run based on the user query.
            You may choose ONE tool or MULTIPLE tools in a meaningful order.

            Available tools and their purposes:

            1) filter  
               Extracts structured metadata from emails (priority, tags, actions).
               Should run BEFORE newsletter or auto if they are used.

            2) newsletter  
               Analyzes newsletters: digest, unsubscribe suggestions, keep suggestions.

            3) content  
               Produces summaries, explanations, overviews, or general analysis.

            4) auto  
               Generates reply drafts or suggested responses.
               Must run AFTER filter if both are used.

            5) key_points  
               Extracts key bullet points AND key tasks (action items) from emails.
               Use when the user asks for key points, main ideas, bullet points, highlights,
               tasks, action items, what needs to be done, required actions, follow-up tasks.

            6) deadlines  
               Extracts deadlines, due dates, submission times.

            General rules:
            - You may choose multiple tools if the query requires multiple types of analysis.
            - Order matters: filter → content → key_points → deadlines → auto → newsletter (as needed).
            - If the user asks for several things (summary + deadlines + tasks), include all relevant tools.
            - If the query is ambiguous, choose the minimal reasonable set of tools.
            - Output STRICTLY valid JSON with the schema:

              {{
                "plan": ["tool_name", "..."]
              }}

            User query: "{query}"
            """
        )

        self.allowed_tools = {
            "newsletter",
            "content",
            "auto",
            "key_points",
            "deadlines",
            "filter",
        }

        # Фиксированный порядок для "всех тулов"
        self.all_tools_order = [
            "content",
            "key_points",
            "deadlines",
            "auto",
            "newsletter",
            "filter",
        ]

    def _is_all_tools_query(self, query: str) -> bool:
        """Жёсткая эвристика: пользователь явно просит вызвать все инструменты."""
        if not query or not isinstance(query, str):
            return False
        q = query.strip().lower()
        triggers = [
            "вызвать все тулы",
            "вызови все тулы",
            "запусти все тулы",
            "run all tools",
            "use all tools",
            "call all tools",
            "invoke all tools",
            "запусти все инструменты",
            "вызвать все инструменты",
            "вызови все инструменты",
        ]
        return any(t in q for t in triggers)

    async def build_plan(self, query: str, user_language: str = "English") -> List[str]:
        query = query or ""
        logger.info("PlanBuilder received query: %r", query)

        # Спец-режим: пользователь явно просит все тулы
        if self._is_all_tools_query(query):
            plan = [t for t in self.all_tools_order if t in self.allowed_tools]
            logger.info("PlanBuilder all-tools heuristic triggered: %s", plan)
            return plan

        prompt = self.prompt_tmpl.format(query=query)

        try:
            # BaseTool.call вернёт dict, соответствующий schema {"plan": ["string"]}
            result = await self.llm.call(
                prompt,
                variables={"query": query},
                user_language=user_language,
            )
            logger.debug("PlanBuilder raw structured result: %r", result)

            plan_raw = result.get("plan", [])
            if isinstance(plan_raw, str):
                # если модель вернула строку типа "filter, content"
                plan = [p.strip() for p in plan_raw.split(",") if p.strip()]
            elif isinstance(plan_raw, list):
                plan = [str(p).strip() for p in plan_raw if str(p).strip()]
            else:
                plan = []
        except Exception as e:
            logger.error("PlanBuilder LLM call failed: %s", e)
            plan = []

        # Фолбек
        if not plan:
            plan = ["content"]

        # Фильтрация по разрешённым тулзам
        plan = [t for t in plan if t in self.allowed_tools]

        logger.info("PlanBuilder final execution plan: %s", plan)
        return plan
