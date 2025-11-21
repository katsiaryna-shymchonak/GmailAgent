"""Base tool class for AI agent tools"""
import json
from typing import Any, Dict, Optional

from langchain_google_genai import ChatGoogleGenerativeAI

from ..config import get_settings

settings = get_settings()


class BaseTool:
    """Base class for all agent tools using LangChain"""
    name = "base"

    def __init__(self, llm: Optional[ChatGoogleGenerativeAI] = None) -> None:
        """
        Initialize tool with LangChain LLM

        Args:
            llm: Optional LangChain LLM instance (creates new if not provided)
        """
        self.llm = llm or ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            temperature=0.2,
            google_api_key=settings.gemini_api_key,
        )

    def _call_model(self, prompt: str, temperature: float = 0.2) -> Dict[str, Any]:
        """
        Call LLM with prompt and return structured JSON response using LangChain

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            Parsed JSON response or raw text if parsing fails
        """
        # Create LLM with specified temperature
        # Check if we can reuse existing LLM
        try:
            current_temp = getattr(self.llm, 'temperature', 0.2)
            if abs(current_temp - temperature) < 0.01:
                llm = self.llm
            else:
                llm = ChatGoogleGenerativeAI(
                    model=settings.gemini_model,
                    temperature=temperature,
                    google_api_key=settings.gemini_api_key,
                )
        except AttributeError:
            # Create new LLM if temperature attribute not available
            llm = ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                temperature=temperature,
                google_api_key=settings.gemini_api_key,
            )

        try:
            # Try structured output first for reliable JSON parsing
            response = llm.with_structured_output(dict).invoke(prompt)
            if isinstance(response, dict):
                return response
        except Exception:
            pass

        # Fallback to regular invocation with JSON parsing
        try:
            response = llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            # Try to parse as JSON
            if isinstance(content, str):
                # Look for JSON in the response
                content = content.strip()
                if content.startswith('{') or content.startswith('['):
                    return json.loads(content)
                # Try to extract JSON from markdown code blocks
                if '```json' in content or '```' in content:
                    import re
                    json_match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])', content, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group(1))

            return {"raw": content}
        except (json.JSONDecodeError, Exception) as e:
            return {"raw": str(response) if 'response' in locals() else str(e)}

