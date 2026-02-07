from __future__ import annotations

import base64
import os
from typing import Any, Dict

import requests


def generate_poster_image(
    *,
    prompt: str,
    size: str = "1024x1024",
    model: str = "gpt-image-1",
    timeout_s: int = 120,
) -> bytes:
    """
    Minimal V1 image generation:
    - Calls OpenAI Images API /v1/images/generations
    - Returns raw image bytes (PNG by default)

    Env:
      OPENAI_API_KEY must be set.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY env var")

    url = "https://api.openai.com/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    body: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "n": 1,
        "output_format": "png",
        "response_format": "b64_json",
    }

    resp = requests.post(url, headers=headers, json=body, timeout=timeout_s)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenAI Images API error {resp.status_code}: {resp.text[:800]}")

    data = resp.json()
    b64 = data["data"][0]["b64_json"]
    return base64.b64decode(b64)
