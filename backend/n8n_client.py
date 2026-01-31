import os
import json
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

    # 3) Same header style as tender_agent_app
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # 4) POST JSON (exactly like your working apps)
    # IMPORTANT: if a proxy redirects a POST, some clients drop the body.
    # Disabling redirects makes this visible.
    resp = requests.post(
        target_url,
        json=payload,
        headers=headers,
        timeout=60,
        allow_redirects=False,
    )

    # 5) Build result with debug fields first
    result: Dict[str, Any] = {}
    result["_debug_target_url"] = target_url
    result["_debug_payload_sent"] = payload
    result["_debug_http_status"] = resp.status_code
    result["_debug_final_url"] = resp.url
    result["_debug_resp_headers"] = dict(resp.headers)
    result["_debug_resp_content_type"] = resp.headers.get("content-type", "")
    result["_debug_resp_text_snippet"] = (resp.text or "")[:400]

    # Fail fast on redirects – this is a common cause of "webhook triggered but empty body".
    if resp.status_code in (301, 302, 303, 307, 308):
        result["_error"] = "n8n returned a redirect; request likely did not reach the webhook handler as intended."
        result["_location"] = resp.headers.get("Location", "")
        return result

    # If n8n returns HTML/text with status 200, that is strong evidence the test webhook is not listening
    # (or you hit a proxy/login/error page) rather than your workflow handler.
    ct = (result.get("_debug_resp_content_type") or "").lower()
    if ct and ("application/json" not in ct):
        result["_error"] = f"Unexpected response Content-Type from n8n: {result['_debug_resp_content_type']}"
        return result

    # Best effort parse JSON response (Respond to Webhook node may return JSON)
    try:
        if (resp.text or "").strip():
            result["_n8n_response_json"] = resp.json()
    except Exception:
        # Keep debug fields; don't crash.
        pass

    return result
