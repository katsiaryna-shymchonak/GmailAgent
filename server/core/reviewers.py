import logging
import json
from typing import Dict, Any

from ..tools.base import BaseTool
from ..config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class QualityReviewer(BaseTool):
    """Reviews agent outputs, scores them, and refines if needed."""

    def __init__(self, model_name: str | None = None):
        schema = {
            "summary": "string",
            "filter_results": [],
            "newsletter_insights": {},
            "auto_replies": [],
            "messages": [],
            "capabilities_tip": "string"
        }
        super().__init__(schema=schema)

    async def score(self, result: Dict[str, Any]) -> int:
        scoring_prompt = (
            "You are a strict reviewer. Evaluate the quality of the following answer on a scale from 1 to 10.\n"
            f"Answer:\n{json.dumps(result, ensure_ascii=False)}"
        )
        try:
            raw = await self._invoke(scoring_prompt)
            text = getattr(raw, "content", str(raw)).strip()

            if text.isdigit():
                score = max(1, min(int(text), 10))
                logger.info("Review score → %d", score)
                return score

            logger.warning("Reviewer returned non-integer: %s", text)
            return 7
        except Exception as e:
            logger.error("Reviewer score failed: %s", e)
            return 7

    async def refine(self, result: Dict[str, Any]) -> Dict[str, Any]:
        refine_prompt = (
            "Rewrite the result to make it more structured, clear, and useful for the user.\n"
            f"Previous result:\n{json.dumps(result, ensure_ascii=False)}"
        )
        try:
            raw = await self._invoke(refine_prompt)
            refined_text = str(getattr(raw, "content", raw)).strip()
            refined = json.loads(refined_text)

            if not isinstance(refined, dict):
                raise ValueError("Refine returned non-dict")

            # Ensure schema completeness
            for key in self.schema.keys():
                if key not in refined:
                    refined[key] = (
                        result.get(key, [] if isinstance(self.schema[key], list)
                                   else {} if isinstance(self.schema[key], dict)
                                   else "")
                    )

            logger.info("Review refined result → %s", json.dumps(refined, ensure_ascii=False, indent=2))
            return refined
        except Exception as e:
            logger.error("Refine failed: %s", e)
            return result
