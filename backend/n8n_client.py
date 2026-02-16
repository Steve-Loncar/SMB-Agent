import os
import requests
from typing import Any, Dict, Literal, Optional


def _load_prompt(filename: str) -> str:
    """Load a prompt .txt file from the prompts/ directory."""
    with open(os.path.join("prompts", filename), encoding="utf-8") as f:
        return f.read().strip()


Mode = Literal["TEST", "LIVE"]
Endpoint = Literal["generate_ads", "generate_image", "scrape_pack", "check_text_blobs", "homepage_summarise", "tier1_summarise"]


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
        N8N_CHECK_TEXT_BLOBS_URL_TEST / _LIVE
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
            ("check_text_blobs", "TEST"): "N8N_CHECK_TEXT_BLOBS_URL_TEST",
            ("check_text_blobs", "LIVE"): "N8N_CHECK_TEXT_BLOBS_URL_LIVE",
            ("homepage_summarise", "TEST"): "N8N_HOMEPAGE_SUMMARISE_URL_TEST",
            ("homepage_summarise", "LIVE"): "N8N_HOMEPAGE_SUMMARISE_URL_LIVE",
            ("tier1_summarise", "TEST"): "N8N_TIER1_SUMMARISE_URL_TEST",
            ("tier1_summarise", "LIVE"): "N8N_TIER1_SUMMARISE_URL_LIVE",
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
                ("check_text_blobs", "TEST"): "/webhook-test/check-text-blobs",
                ("check_text_blobs", "LIVE"): "/webhook/check-text-blobs",
                ("homepage_summarise", "TEST"): "/webhook-test/SMB-homepage-summarise",
                ("homepage_summarise", "LIVE"): "/webhook/SMB-homepage-summarise",
                ("tier1_summarise", "TEST"): "/webhook-test/SMB-tier1-summariser",
                ("tier1_summarise", "LIVE"): "/webhook/SMB-tier1-summariser",
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


def call_n8n_check_text_blobs(
    *,
    url: str,
    scrape_pack: Any,
    mode: Mode = "TEST",
    webhook_url: Optional[str] = None,
) -> dict:
    """
    POST payload to n8n /check-text-blobs.
    AI "2nd pass" over deterministic scrape-pack output.
    """
    target_url = resolve_n8n_webhook("check_text_blobs", mode, override_url=webhook_url)
    headers = _tender_headers()

    payload = {
        "payload_type": "smb_check_text_blobs",
        "url": url,
        "scrape_pack": scrape_pack,
    }

    req_timeout = (10, 180)
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


def call_n8n_homepage_summarise(
    *,
    url: str,
    homepage_markdown: str,
    page_summaries: list[dict] | None = None,
    mode: Mode = "TEST",
    webhook_url: Optional[str] = None,
) -> dict:
    """
    POST homepage markdown + page snippets to n8n /SMB-homepage-summarise.
    Returns business summary (name_guess, category, value_prop, target_customer, tone).
    """
    target_url = resolve_n8n_webhook("homepage_summarise", mode, override_url=webhook_url)
    headers = _tender_headers()

    # Format page snippets from tier1/tier2 summariser into a text block
    snippets_text = ""
    for ps in (page_summaries or []):
        if not isinstance(ps, dict):
            continue
        title = ps.get("page_title", "")
        p_url = ps.get("page_url", "")
        snips = ps.get("ad_snippets", [])
        if not isinstance(snips, list):
            snips = []
        snip_lines = "\n".join(f"  - {s}" for s in snips if isinstance(s, str) and s.strip())
        if title or snip_lines:
            snippets_text += f"\n{title} ({p_url})\n{snip_lines}\n"

    user_template = _load_prompt("smb_homepage_summarise_user.txt")
    prompt_user = user_template.format(
        url=url,
        homepage_markdown=(homepage_markdown or "")[:30000],
        page_snippets=snippets_text.strip() if snippets_text.strip() else "(no additional pages scraped)",
    )

    payload = {
        "payload_type": "smb_homepage_summarise",
        "url": url,
        "homepage_markdown": (homepage_markdown or "")[:30000],
        "prompt_system": _load_prompt("smb_homepage_summarise_system.txt"),
        "prompt_user": prompt_user,
    }

    req_timeout = (10, 120)
    resp = requests.post(target_url, headers=headers, json=payload, timeout=req_timeout)

    result: Dict[str, Any] = {}
    result["_debug_target_url"] = target_url
    result["_debug_payload_sent"] = {**payload, "homepage_markdown": f"({len(payload['homepage_markdown'])} chars)"}
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


def call_n8n_tier1_summarise(
    *,
    url: str,
    tier1_urls: list[str],
    tier2_urls: list[str] = None,
    tier1_page_summaries: list[dict] = None,
    business_summary: dict,
    mode: Mode = "TEST",
    webhook_url: Optional[str] = None,
) -> dict:
    """
    POST tier 1 URLs + business summary to n8n /SMB-tier1-summariser.
    Also sends tier2_urls and decision prompts so the workflow can
    optionally scrape high-value tier 2 pages.
    Returns page_summaries + optional tier2_page_summaries + tier2_decision.
    """
    target_url = resolve_n8n_webhook("tier1_summarise", mode, override_url=webhook_url)
    headers = _tender_headers()

    bs = business_summary or {}
    user_template = _load_prompt("smb_tier1_summarise_user.txt")
    prompt_user = user_template.format(
        url=url,
        name_guess=bs.get("name_guess", ""),
        category=bs.get("category", ""),
        value_prop=bs.get("value_prop", ""),
        target_customer=bs.get("target_customer", ""),
        tone=bs.get("tone", ""),
    )

    # Build a summary of existing snippets for the tier 2 decision agent
    snippets_summary = ""
    for ps in (tier1_page_summaries or []):
        if isinstance(ps, dict):
            title = ps.get("page_title", "")
            snips = ps.get("ad_snippets", [])
            if snips:
                snippets_summary += f"{title}: {'; '.join(str(s) for s in snips)}\n"

    decision_user_template = _load_prompt("smb_tier2_decision_user.txt")
    decision_prompt_user = decision_user_template.format(
        url=url,
        name_guess=bs.get("name_guess", ""),
        category=bs.get("category", ""),
        value_prop=bs.get("value_prop", ""),
        target_customer=bs.get("target_customer", ""),
        tone=bs.get("tone", ""),
        tier1_snippets_summary=snippets_summary or "(none yet — tier 1 extraction in progress)",
        tier2_urls="\n".join(tier2_urls or []),
    )

    payload = {
        "payload_type": "smb_tier1_summarise",
        "url": url,
        "tier1_urls": tier1_urls or [],
        "tier2_urls": tier2_urls or [],
        "business_summary": bs,
        "prompt_system": _load_prompt("smb_tier1_summarise_system.txt"),
        "prompt_user": prompt_user,
        "decision_prompt_system": _load_prompt("smb_tier2_decision_system.txt"),
        "decision_prompt_user": decision_prompt_user,
    }

    req_timeout = (10, 180)
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

    # scrape-pack can legitimately take longer on slow/old SMB sites (multi-page fetch)
    # Keep connect timeout tight; extend read timeout to avoid false negatives.
    req_timeout = (10, 180)
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
