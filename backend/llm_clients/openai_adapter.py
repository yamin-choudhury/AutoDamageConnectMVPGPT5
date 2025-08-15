from __future__ import annotations
import os, time, random, threading, base64
from pathlib import Path
from typing import List, Optional

try:
    from openai import OpenAI  # type: ignore
except Exception as e:  # pragma: no cover
    OpenAI = None  # type: ignore

try:
    from PIL import Image  # type: ignore
except Exception:
    Image = None  # type: ignore


def _encode_image_data_url(p: Path, max_px: int = 1600, quality: int = 80) -> str:
    if Image is None:
        b = p.read_bytes()
        return "data:image/jpeg;base64," + base64.b64encode(b).decode()
    img = Image.open(p).convert("RGB")
    if max(img.size) > max_px:
        img.thumbnail((max_px, max_px))
    import io
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    buf.seek(0)
    return "data:image/jpeg;base64," + base64.b64encode(buf.read()).decode()


class OpenAIAdapter:
    def __init__(self):
        if OpenAI is None:
            raise RuntimeError("openai package not available")
        self.client = OpenAI()
        # Tunables
        self.vision_model = os.getenv("OPENAI_VISION_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o"))
        self.text_model = os.getenv("OPENAI_TEXT_MODEL", self.vision_model)
        self.max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "5"))
        self.backoff_base = float(os.getenv("OPENAI_BACKOFF_BASE", "0.5"))
        self.concurrency = int(os.getenv("OPENAI_CONCURRENCY", "4"))
        self._sem = threading.Semaphore(self.concurrency)

    def vision_json(
        self,
        prompt: str,
        image_paths: List[Path],
        temperature: float = 0.2,
        max_images: Optional[int] = None,
    ) -> str:
        # Optional capping done here as well
        use_paths = image_paths[:]
        if max_images is not None and len(use_paths) > max_images:
            use_paths = use_paths[:max_images]

        user_parts: list[dict] = [{"type": "text", "text": "Please analyze all images and reply with JSON only."}]
        for p in use_paths:
            user_parts.append({"type": "image_url", "image_url": {"url": _encode_image_data_url(p)}})

        with self._sem:
            last_err: Exception | None = None
            for attempt in range(self.max_retries):
                try:
                    resp = self.client.chat.completions.create(
                        model=self.vision_model,
                        messages=[
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": user_parts},
                        ],
                        max_tokens=6144,
                        temperature=temperature,
                    )
                    return (resp.choices[0].message.content or "").strip()
                except Exception as e:
                    last_err = e
                    if attempt < self.max_retries - 1:
                        sleep_s = self.backoff_base * (2 ** attempt) + random.uniform(0, 0.25)
                        time.sleep(sleep_s)
                    else:
                        raise
            # Should not reach here
            if last_err:
                raise last_err
            return ""

    def text(self, prompt: str, temperature: float = 0.2) -> str:
        with self._sem:
            last_err: Exception | None = None
            for attempt in range(self.max_retries):
                try:
                    resp = self.client.chat.completions.create(
                        model=self.text_model,
                        messages=[
                            {"role": "system", "content": "You are a concise assistant."},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=2048,
                        temperature=temperature,
                    )
                    return (resp.choices[0].message.content or "").strip()
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
