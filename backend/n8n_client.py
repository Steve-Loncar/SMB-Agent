import os
import json
import requests
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def call_n8n_generate_ads(
    scraped_text: str,
    image_urls: list[str],
    url: str,
    *,
    webhook_url: str | None = None,
) -> dict:
    """
    Sends scraped content to an n8n webhook.
    For now, send a very simple payload and don't try to be clever.
    """

    def _canonicalize_webhook_url(u: str) -> str:
        # Avoid redirect pitfalls: normalize whitespace, and ensure no accidental double slashes.
        u = (u or "").strip()
        if not u:
            return u
        parts = urlsplit(u)
        # Normalize path: remove trailing spaces, but KEEP a trailing slash if provided
        path = parts.path or ""
        path = "/" + path.lstrip("/")  # ensure exactly one leading slash
        return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))

    # 1) Decide URL: prefer explicit argument, else env var, else TEST endpoint
    if webhook_url:
        target_url = webhook_url
    else:
        target_url = (
            os.getenv("N8N_WEBHOOK_URL")
            or "https://fpgconsulting.app.n8n.cloud/webhook-test/generate-ads"
        )
    target_url = _canonicalize_webhook_url(target_url)

    # 2) Build a flat, boring payload
    payload = {
        "payload_type": "smb_ad_agent_test",
        "url": url,
        # IMPORTANT: match what SMB_scrape.json references in n8n ({{$json.scraped_text}})
        # Keep it bounded to avoid huge payloads while debugging.
        "scraped_text": (scraped_text or "")[:20000],
        "scraped_text_len": len(scraped_text or ""),
        "image_count": len(image_urls or []),
        "sample_text": (scraped_text or "")[:500],  # keep for quick inspection
    }

    # 3) Same header style as tender_agent_app
    headers = {
        "Content-Type": "application/json",
    }

    # 4) POST JSON (exactly like your working apps)
    resp = requests.post(
        target_url,
        json=payload,
        headers=headers,
        timeout=60,
    )

    # 5) Best-effort JSON parse, but do NOT treat empty body as fatal
    text = (resp.text or "").strip()
    result: dict = {}
    if text:
        try:
            result = resp.json()
        except Exception:
            result = {}

    # Always include the outbound payload for debugging in the caller
    result.setdefault("_debug_payload_sent", payload)
    result.setdefault("_debug_target_url", target_url)
    result.setdefault("_debug_http_status", resp.status_code)
    result.setdefault("_debug_resp_headers", dict(resp.headers))
    # If a proxy redirected you, this will prove it immediately.
    result.setdefault("_debug_redirect_count", len(resp.history))
    result.setdefault("_debug_final_url", resp.url)
    return result
