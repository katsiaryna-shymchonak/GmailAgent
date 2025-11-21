"""Embedding service for generating vector embeddings"""
import os
from typing import Any, List

import google.generativeai as genai

from ..config import get_settings

settings = get_settings()

# Configure Gemini client for embeddings
api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY is missing")

genai.configure(api_key=api_key)


def _extract_vector(result: Any) -> List[float]:
    """
    Normalize various response shapes from google.generativeai embed_content.
    
    Handles different response formats:
    - {'embedding': {'values': [...]}}
    - {'embeddings': [{'values': [...]}, ...]}
    - {'embedding': [...]}
    - [{'values': [...]}, ...]  # take first
    - direct list[float]
    """
    if result is None:
        raise RuntimeError("Empty embedding response")
    
    # Direct list of floats
    if isinstance(result, list) and result and isinstance(result[0], (int, float)):
        return result  # type: ignore[return-value]
    
    if isinstance(result, dict):
        if "embedding" in result:
            emb = result["embedding"]
            if isinstance(emb, dict) and "values" in emb:
                return emb["values"]
            if isinstance(emb, list):
                return emb
        if "embeddings" in result and isinstance(result["embeddings"], list):
            first = result["embeddings"][0]
            if isinstance(first, dict) and "values" in first:
                return first["values"]
            if isinstance(first, list):
                return first
    
    if isinstance(result, list) and result and isinstance(result[0], dict) and "values" in result[0]:
        return result[0]["values"]
    
    raise RuntimeError(f"Unrecognized embedding response shape: {type(result)}")


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a list of texts using Gemini API"""
    if not texts:
        return []

    embeddings: List[List[float]] = []
    for text in texts:
        result = genai.embed_content(
            model=settings.embedding_model,
            content=text,
        )
        embeddings.append(_extract_vector(result))
    return embeddings

