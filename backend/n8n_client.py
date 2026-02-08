import os
import requests
from typing import Any, Dict, Literal, Optional


Mode = Literal["TEST", "LIVE"]
Endpoint = Literal["generate_ads", "generate_image", "scrape_pack"]


def resolve_n8n_webhook(endpoint: Endpoint, mode: Mode, *, override_url: Optional[str] = None) -> str:
    """
    Single source of truth for webhook URLs.

    Env:
      N8N_BASE_URL (optional, defaults to your n8n cloud)
      N8N_WEBHOOK_SECRET (optional, sent as X-Webhook-Secret)

      Optional per-endpoint override env vars (if you want them later):
        N8N_GENERATE_ADS_URL_TEST / _LIVE
        N8N_GENERATE_IMAGE_URL_TEST / _LIVE
        N8N_SCRAPE_PACK_URL_TEST / _LIVE
    """
    if override_url:
        target_url = override_url.strip()
    else:
        base = (os.getenv("N8N_BASE_URL") or "https://fpgconsulting.app.n8n.cloud").rstrip("/")

        # Optional explicit full URL overrides (handy for quick swaps)
        env_map = {
            ("generate_ads", "TEST"): "N8N_GENERATE_ADS_URL_TEST",
            ("generate_ads", "LIVE"): "N8N_GENERATE_ADS_URL_LIVE",
            ("generate_image", "TEST"): "N8N_GENERATE_IMAGE_URL_TEST",
            ("generate_image", "LIVE"): "N8N_GENERATE_IMAGE_URL_LIVE",
            ("scrape_pack", "TEST"): "N8N_SCRAPE_PACK_URL_TEST",
            ("scrape_pack", "LIVE"): "N8N_SCRAPE_PACK_URL_LIVE",
        }
        env_key = env_map[(endpoint, mode)]
        explicit = (os.getenv(env_key) or "").strip()
        if explicit:
            target_url = explicit
        else:
            # Default paths (your current conventions)
            paths = {
                ("generate_ads", "TEST"): "/webhook-test/generate-ads",
                ("generate_ads", "LIVE"): "/webhook/generate-ads",
                ("generate_image", "TEST"): "/webhook-test/generate-image",
                ("generate_image", "LIVE"): "/webhook/generate-image",
                ("scrape_pack", "TEST"): "/webhook-test/scrape-pack",
                ("scrape_pack", "LIVE"): "/webhook/scrape-pack",
            }
            target_url = base + paths[(endpoint, mode)]

    # Hard fail if URL isn't exactly what we expect (prevents "posting to nowhere")
    if (
        not isinstance(target_url, str)
        or not target_url.startswith("https://")
        or "/webhook" not in target_url
    ):
        raise RuntimeError(f"Invalid n8n webhook URL: {repr(target_url)}")

    return target_url


def _tender_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    # Mirror Tender / Echo pattern: secret optional but supported
    secret = (os.getenv("WEBHOOK_SECRET") or os.getenv("N8N_WEBHOOK_SECRET") or "").strip()
    if secret:
        headers["X-Webhook-Secret"] = secret
    return headers


def call_n8n_generate_ads(
    scraped_text: str,
    image_urls: list[str],
    url: str,
    *,
    mode: Mode = "TEST",
    webhook_url: Optional[str] = None,
) -> dict:
    """
    POST payload to n8n webhook. Returns debug-rich dict including:
    - ok (bool)
    - status_code
    - response_json (if parseable)
    - response_text_snippet
    - sent_payload (echo)
    """
    # Sends scraped content to an n8n webhook.
    # For now, send a very simple payload and don't try to be clever.

    # 1) Decide URL from single source of truth
    target_url = resolve_n8n_webhook("generate_ads", mode, override_url=webhook_url)

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
    headers = _tender_headers()

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


def call_n8n_generate_image(
    prompt: str,
    size: str = "1024x1024",
    *,
    mode: Mode = "TEST",
    webhook_url: Optional[str] = None,
) -> dict:
    """
    POST an image prompt to n8n /generate-image. Expects response:
      { image_b64: "...", mime: "image/png" }
    """
    url = resolve_n8n_webhook("generate_image", mode, override_url=webhook_url)
    headers = _tender_headers()

    payload = {"prompt": prompt, "size": size}
    r = requests.post(url, json=payload, headers=headers, timeout=120)
    out = {"ok": (200 <= r.status_code < 300), "status_code": r.status_code, "sent_payload": payload}
    out["response_text_snippet"] = (r.text or "")[:1200]
    try:
        out["response_json"] = r.json()
    except Exception:
        out["response_json"] = None
    return out


def call_n8n_scrape_pack(
    *,
    url: str,
    depth: str = "homepage_plus",
    max_pages: int = 3,
    mode: Mode = "TEST",
    webhook_url: Optional[str] = None,
) -> dict:
    """
    POST payload to n8n /scrape-pack.
    This is wiring-friendly: it returns the same debug envelope shape as generate_ads.
    """
    target_url = resolve_n8n_webhook("scrape_pack", mode, override_url=webhook_url)
    headers = _tender_headers()

    payload = {
        "payload_type": "smb_scrape_pack",
        "url": url,
        "depth": depth,
        "max_pages": int(max_pages),
    }

    req_timeout = (10, 60)
    resp = requests.post(target_url, headers=headers, json=payload, timeout=req_timeout)

    result: Dict[str, Any] = {}
    result["_debug_target_url"] = target_url
    result["_debug_payload_sent"] = payload
    result["_debug_http_status"] = resp.status_code
    result["_debug_final_url"] = resp.url
    result["_debug_resp_headers"] = dict(resp.headers)
    result["_debug_resp_content_type"] = resp.headers.get("content-type", "")
    result["_debug_resp_text_snippet"] = (resp.text or "")[:400]

    if resp.status_code != 200:
        ct = resp.headers.get("Content-Type", "")
        body = (resp.text or "")
        result["_error"] = (
            f"n8n returned HTTP {resp.status_code} (Content-Type: {ct}, body_len: {len(body)}): "
            f"{body[:800]}"
        )
        return result

    try:
        if (resp.text or "").strip():
            result["_n8n_response_json"] = resp.json()
    except Exception:
        pass

    return result
