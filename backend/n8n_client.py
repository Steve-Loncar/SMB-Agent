import os
import requests
from typing import Any, Dict


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

    # Hard fail if URL isn't exactly what we expect (prevents "posting to nowhere")
    if not isinstance(target_url, str) or not target_url.startswith("https://") or "/webhook" not in target_url:
        raise RuntimeError(f"Invalid n8n webhook URL: {repr(target_url)}")

    # Mirror Tender / Echo pattern: secret optional but supported
    webhook_secret = os.getenv("WEBHOOK_SECRET", "")

    # 2) Build a flat, boring payload
    payload = {
        "payload_type": "smb_ad_agent_test",
        "url": url,
        # IMPORTANT: match what SMB_scrape.json references in n8n ({{$json.scraped_text}})
        # Keep it bounded to avoid huge payloads while debugging.
        "scraped_text": (scraped_text or "")[:20000],
        "scraped_text_len": len(scraped_text or ""),
        "image_count": len(image_urls or []),
        "image_urls": image_urls or [],
        "sample_text": (scraped_text or "")[:500],  # keep for quick inspection
    }

    # EXACT Tender-style headers (no Accept)
    headers = {"Content-Type": "application/json"}
    if webhook_secret:
        headers["X-Webhook-Secret"] = webhook_secret

    # EXACT Tender-style timeout shape: (connect, read)
    req_timeout = (10, 60)
    resp = requests.post(target_url, headers=headers, json=payload, timeout=req_timeout)

    # Build result with debug fields first
    result: Dict[str, Any] = {}
    result["_debug_target_url"] = target_url
    result["_debug_payload_sent"] = payload
    result["_debug_http_status"] = resp.status_code
    result["_debug_final_url"] = resp.url
    result["_debug_resp_headers"] = dict(resp.headers)
    result["_debug_resp_content_type"] = resp.headers.get("content-type", "")
    result["_debug_resp_text_snippet"] = (resp.text or "")[:400]

    # EXACT Tender-style failure handling: non-200 => surface body snippet
    if resp.status_code != 200:
        ct = resp.headers.get("Content-Type", "")
        body = (resp.text or "")
        result["_error"] = (
            f"n8n returned HTTP {resp.status_code} (Content-Type: {ct}, body_len: {len(body)}): "
            f"{body[:800]}"
        )
        return result

    # Best effort parse JSON response (Respond to Webhook node may return JSON)
    try:
        if (resp.text or "").strip():
            result["_n8n_response_json"] = resp.json()
    except Exception:
        # Keep debug fields; don't crash.
        pass

    return result
