from __future__ import annotations
import os
from .openai_adapter import OpenAIAdapter
from .gemini_adapter import GeminiAdapter


def create_vision_client():
    provider = (os.getenv("MODEL_PROVIDER") or os.getenv("LLM_PROVIDER") or "openai").strip().lower()
    if provider in ("gemini", "google", "googleai", "google-ai"):
        return GeminiAdapter()
    # default
    return OpenAIAdapter()
