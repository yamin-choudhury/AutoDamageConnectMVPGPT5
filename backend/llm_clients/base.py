from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Protocol


class LLMVisionClient(Protocol):
    """Provider-agnostic interface for vision and text generation."""

    def vision_json(
        self,
        prompt: str,
        image_paths: List[Path],
        temperature: float = 0.2,
        max_images: Optional[int] = None,
    ) -> str:
        """Generate a JSON (as string) response given a prompt and images.
        Implementations should enforce JSON-only responses when possible.
        """
        ...

    def text(self, prompt: str, temperature: float = 0.2) -> str:
        """Generate plain text from a prompt."""
        ...
