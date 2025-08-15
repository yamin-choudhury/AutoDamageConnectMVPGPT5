from __future__ import annotations
import os, time, random, threading, base64
from pathlib import Path
from typing import List, Optional

try:
    import google.generativeai as genai  # type: ignore
except Exception as e:  # pragma: no cover
    genai = None  # type: ignore

try:
    from PIL import Image  # type: ignore
except Exception:
    Image = None  # type: ignore


def _read_image_bytes_resized(p: Path, max_px: int = 1600, quality: int = 80) -> bytes:
    if Image is None:
        return p.read_bytes()
    img = Image.open(p).convert("RGB")
    if max(img.size) > max_px:
        img.thumbnail((max_px, max_px))
    import io
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    buf.seek(0)
    return buf.read()


class GeminiAdapter:
    def __init__(self):
        if genai is None:
            raise RuntimeError("google-generativeai package not available")
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY/GEMINI_API_KEY is required for GeminiAdapter")
        genai.configure(api_key=api_key)
        self.vision_model_name = os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")
        self.text_model_name = os.getenv("GEMINI_TEXT_MODEL", self.vision_model_name)
        self.max_retries = int(os.getenv("GEMINI_MAX_RETRIES", os.getenv("OPENAI_MAX_RETRIES", "5")))
        self.backoff_base = float(os.getenv("GEMINI_BACKOFF_BASE", os.getenv("OPENAI_BACKOFF_BASE", "0.5")))
        self.concurrency = int(os.getenv("GEMINI_CONCURRENCY", os.getenv("OPENAI_CONCURRENCY", "4")))
        self._sem = threading.Semaphore(self.concurrency)

        # Pre-create models
        self._vision_model = genai.GenerativeModel(self.vision_model_name)
        self._text_model = genai.GenerativeModel(self.text_model_name)

        # Defaults
        self.response_mime_type = os.getenv("GEMINI_RESPONSE_MIME", "application/json")

    def _images_to_parts(self, paths: List[Path], max_images: Optional[int]) -> List[dict]:
        use_paths = paths[:]
        if max_images is not None and len(use_paths) > max_images:
            use_paths = use_paths[:max_images]
        parts: List[dict] = []
        for p in use_paths:
            b = _read_image_bytes_resized(p)
            parts.append({
                "mime_type": "image/jpeg",
                "data": base64.b64encode(b).decode(),
            })
        return parts

    def vision_json(
        self,
        prompt: str,
        image_paths: List[Path],
        temperature: float = 0.2,
        max_images: Optional[int] = None,
    ) -> str:
        inputs: List = [prompt]
        inputs.extend(self._images_to_parts(image_paths, max_images))
        gen_cfg = {
            "temperature": temperature,
            "response_mime_type": self.response_mime_type,
        }
        with self._sem:
            last_err: Exception | None = None
            for attempt in range(self.max_retries):
                try:
                    resp = self._vision_model.generate_content(
                        inputs,
                        generation_config=gen_cfg,
                    )
                    # For SDK v0.7+, text is at resp.text
                    return (getattr(resp, "text", None) or "").strip()
                except Exception as e:
                    last_err = e
                    if attempt < self.max_retries - 1:
                        sleep_s = self.backoff_base * (2 ** attempt) + random.uniform(0, 0.25)
                        time.sleep(sleep_s)
                    else:
                        raise
            if last_err:
                raise last_err
            return ""

    def text(self, prompt: str, temperature: float = 0.2) -> str:
        gen_cfg = {
            "temperature": temperature,
            "response_mime_type": "text/plain",
        }
        with self._sem:
            last_err: Exception | None = None
            for attempt in range(self.max_retries):
                try:
                    resp = self._text_model.generate_content(
                        prompt,
                        generation_config=gen_cfg,
                    )
                    return (getattr(resp, "text", None) or "").strip()
                except Exception as e:
                    last_err = e
                    if attempt < self.max_retries - 1:
                        sleep_s = self.backoff_base * (2 ** attempt) + random.uniform(0, 0.25)
                        time.sleep(sleep_s)
                    else:
                        raise
            if last_err:
                raise last_err
            return ""
