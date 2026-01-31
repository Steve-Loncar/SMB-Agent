import os
import json
import requests


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

    # 1) Decide URL: prefer explicit argument, else env var, else TEST endpoint
    if webhook_url:
        target_url = webhook_url
    else:
        target_url = (
            os.getenv("N8N_WEBHOOK_URL")
            or "https://fpgconsulting.app.n8n.cloud/webhook-test/generate-ads"
        )

    # 2) Build a flat, boring payload
    payload = {
        "payload_type": "smb_ad_agent_test",
        "url": url,
        "scraped_text_len": len(scraped_text or ""),
        "image_count": len(image_urls or []),
        "sample_text": (scraped_text or "")[:500],
    }

    # 3) Same header style as tender_agent_app
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
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
    if not text:
        return {}

    try:
        return resp.json()
    except Exception:
        return {}
