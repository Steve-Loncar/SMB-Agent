import json
import os
import requests
from typing import Any, Dict, Literal, Optional


def _load_prompt(filename: str) -> str:
    """Load a prompt .txt file from the prompts/ directory."""
    with open(os.path.join("prompts", filename), encoding="utf-8") as f:
        return f.read().strip()


Mode = Literal["TEST", "LIVE"]
Endpoint = Literal["generate_ads", "generate_image", "generate_poster", "scrape_pack", "check_text_blobs", "homepage_summarise", "tier1_summarise", "image_hunt", "generate_ad_concepts"]


# n8n webhook ID mapping (from .n8n-state.json webhook nodes)
# Maps path -> webhook ID for correct n8n cloud webhook URLs
WEBHOOK_IDS = {
    "SMB-generate-ad-concepts": "f1c1027f-7f30-4778-9e86-50d3eec43abb",  # zRiOBZzZe1xC2s4o
    "check-text-blobs": "dd8ce2f3-ccd9-46c3-a98f-3ad205206af0",  # MPLFXEKhILpVNwJE
    "generate-image": "c0a3cdfa-59d0-4ff7-a159-de6404b3a52d",  # LwppGj55f48uEPcm (smb_image_gen)
    "scrape-pack": "8f48c91d-fd36-44fb-8f81-35cbf52dec3f",  # MOC3yN0C7ke04nM4
    "SMB-image-hunt": "f50e2198-bc22-4bdf-a4de-cec065a6b0d9",  # Q5kdwj9M7VlCwX2Z
    "SMB-homepage-summarise": "2cab9d6a-e4cd-48bc-bdbe-1d3f9200e051",  # ykqSvp3N92Yq6GjM
    "SMB-tier1-summariser": "b49fa9a7-a057-44b0-8475-bbe71b5c69b7",  # rJmG2127XE4XU3Zs
}


def resolve_n8n_webhook(endpoint: Endpoint, mode: Mode, *, override_url: Optional[str] = None) -> str:
    """
    Single source of truth for webhook URLs.
    Uses webhookId format (required for n8n cloud).

    Env:
      N8N_BASE_URL (optional, defaults to your n8n cloud)
      N8N_WEBHOOK_SECRET (optional, sent as X-Webhook-Secret)

      Optional per-endpoint override env vars:
        N8N_GENERATE_ADS_URL_TEST / _LIVE
        N8N_GENERATE_IMAGE_URL_TEST / _LIVE, etc.
    """
    if override_url:
        target_url = override_url.strip()
    else:
        base = (os.getenv("N8N_BASE_URL") or "https://fpgconsulting.app.n8n.cloud").rstrip("/")

        # Optional explicit full URL overrides
        env_map = {
            ("generate_ads", "TEST"): "N8N_GENERATE_ADS_URL_TEST",
            ("generate_ads", "LIVE"): "N8N_GENERATE_ADS_URL_LIVE",
            ("generate_ad_concepts", "TEST"): "N8N_GENERATE_AD_CONCEPTS_URL_TEST",
            ("generate_ad_concepts", "LIVE"): "N8N_GENERATE_AD_CONCEPTS_URL_LIVE",
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
            ("image_hunt", "TEST"): "N8N_IMAGE_HUNT_URL_TEST",
            ("image_hunt", "LIVE"): "N8N_IMAGE_HUNT_URL_LIVE",
            ("generate_poster", "TEST"): "N8N_GENERATE_POSTER_URL_TEST",
            ("generate_poster", "LIVE"): "N8N_GENERATE_POSTER_URL_LIVE",
        }
        env_key = env_map[(endpoint, mode)]
        explicit = (os.getenv(env_key) or "").strip()
        if explicit:
            target_url = explicit
        else:
            # Webhook paths and their IDs
            webhook_paths = {
                "generate_ads": "SMB-generate-ad-concepts",
                "generate_ad_concepts": "SMB-generate-ad-concepts",
                "generate_image": "generate-image",
                "generate_poster": "generate-image",
                "scrape_pack": "scrape-pack",
                "check_text_blobs": "check-text-blobs",
                "homepage_summarise": "SMB-homepage-summarise",
                "tier1_summarise": "SMB-tier1-summariser",
                "image_hunt": "SMB-image-hunt",
            }
            path = webhook_paths.get(endpoint)
            webhook_id = WEBHOOK_IDS.get(path) if path else None
            
            if not webhook_id:
                raise RuntimeError(f"Unknown webhook ID for endpoint {endpoint}")
            
            # Use webhookId format for n8n cloud
            target_url = f"{base}/webhook/{webhook_id}"

    # Hard fail if URL isn't exactly what we expect (prevents "posting to nowhere")
    if (
        not isinstance(target_url, str)
        or not target_url.startswith("https://")
        or "/webhook/" not in target_url
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
    *,
    url: str,
    scraped_text: str = "",
    image_urls: list[str] | None = None,
    homepage_markdown: str = "",
    page_summaries: list[dict] | None = None,
    business_summary: dict | None = None,
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

    # Format page snippets into a readable block (same pattern as homepage_summarise)
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

    user_template = _load_prompt("smb_generate_ads_user.txt")
    prompt_user = user_template.format(
        url=url,
        business_summary_json=json.dumps(business_summary or {}, ensure_ascii=False, indent=2),
        homepage_markdown=(homepage_markdown or "")[:30000],
        page_snippets=snippets_text.strip() if snippets_text.strip() else "(no tier snippets provided)",
        image_urls=json.dumps(image_urls or [], ensure_ascii=False),
    )

    payload = {
        "payload_type": "smb_generate_ads_v2",
        "url": url,
        # Keep legacy fields for backward compatibility / debugging
        "scraped_text": (scraped_text or "")[:20000],
        "scraped_text_len": len(scraped_text or ""),
        "sample_text": (scraped_text or "")[:500],
        # New, richer inputs
        "homepage_markdown": (homepage_markdown or "")[:30000],
        "page_summaries": page_summaries or [],
        "business_summary": business_summary or {},
        "image_urls": image_urls or [],
        "image_count": len(image_urls or []),
        # Prompts (consistent with other workflows)
        "prompt_system": _load_prompt("smb_generate_ads_system.txt"),
        "prompt_user": prompt_user,
    }

    # EXACT Tender-style headers (no Accept)
    headers = _tender_headers()

    # EXACT Tender-style timeout shape: (connect, read)
    req_timeout = (10, 180)
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


def call_n8n_generate_poster(
    *,
    poster_concept: dict,
    guidelines: dict,
    visual_images: list[dict],
    business_summary: dict | None = None,
    mode: Mode = "TEST",
    webhook_url: Optional[str] = None,
) -> dict:
    """
    POST structured data to n8n poster generation workflow.
    Triggers workflow execution directly via the n8n API.
    
    Three-stage flow in n8n:
      (1) LLM selects best images from enriched visual_images (with type/cropping/layout metadata)
      (2) LLM (vision-enabled) generates poster prompt, seeing the hero image directly
      (3) gpt-image-1 generates background plate using hero image as reference
    Returns { image_b64, mime, selected_images, poster_metadata }.
    """
    # If webhook URL provided, use the old webhook method
    if webhook_url:
        target_url = webhook_url.strip()
        headers = _tender_headers()
    else:
        # Use n8n API to trigger workflow directly (more reliable for n8n cloud)
        # This executes the workflow and waits for completion
        n8n_host = (os.getenv("N8N_BASE_URL") or "https://fpgconsulting.app.n8n.cloud").rstrip("/")
        
        # Get API key from environment or .vscode/settings.json
        api_key = os.getenv("N8N_API_KEY")
        if not api_key:
            try:
                with open(".vscode/settings.json", "r") as f:
                    vscode_settings = json.load(f)
                    api_key = vscode_settings.get("n8n.apiKey", "")
            except Exception:
                api_key = ""
        
        if not api_key:
            raise RuntimeError("N8N_API_KEY not found in environment or .vscode/settings.json")
        
        workflow_id = "LwppGj55f48uEPcm"  # smb_image_gen workflow ID
        target_url = f"{n8n_host}/api/v1/workflows/{workflow_id}/execute"
        headers = {
            "Content-Type": "application/json",
            "X-N8N-API-KEY": api_key,
        }
    
    bs = business_summary or {}

    # Stage 1 prompts: image selection — pass enriched image objects (not bare URLs)
    sel_system = _load_prompt("smb_image_selection_system.txt")
    sel_user_template = _load_prompt("smb_image_selection_user.txt")
    sel_user = (
        sel_user_template
        .replace("{poster_concept}", json.dumps(poster_concept, ensure_ascii=False, indent=2))
        .replace("{guidelines}", json.dumps(guidelines, ensure_ascii=False, indent=2))
        .replace("{visual_images}", json.dumps(visual_images, ensure_ascii=False, indent=2))
    )

    # Stage 2 prompts: poster prompt gen (template — n8n substitutes {selected_images} after stage 1)
    poster_system = _load_prompt("smb_poster_gen_system.txt")
    poster_user_template = (
        _load_prompt("smb_poster_gen_user.txt")
        .replace("{business_summary}", json.dumps(bs, ensure_ascii=False, indent=2))
    )

    # Bare URLs for n8n fallback / debug
    image_urls = [im.get("url", "") for im in visual_images if isinstance(im, dict) and im.get("url")]

    payload = {
        "poster_concept": poster_concept,
        "guidelines": guidelines,
        "business_summary": bs,
        "visual_images": visual_images,
        "image_urls": image_urls,
        "prompt_system_selection": sel_system,
        "prompt_user_selection": sel_user,
        "prompt_system_poster": poster_system,
        "prompt_user_poster_template": poster_user_template,
    }

    if webhook_url:
        # Legacy webhook mode
        r = requests.post(target_url, json=payload, headers=headers, timeout=(10, 180))
    else:
        # n8n API execute mode (waits for completion, returns full execution result)
        r = requests.post(target_url, json=payload, headers=headers, timeout=(10, 300))
    
    out: Dict[str, Any] = {
        "ok": (200 <= r.status_code < 300),
        "status_code": r.status_code,
        "_debug_target_url": target_url,
        "_debug_payload_keys": list(payload.keys()),
        "_debug_image_url_count": len(visual_images),
    }
    out["response_text_snippet"] = (r.text or "")[:1200]
    
    if not out["ok"]:
        return out
    
    try:
        resp_json = r.json()
        # n8n /execute API returns the full execution result
        # We need to extract the final output data
        if isinstance(resp_json, dict) and "data" in resp_json:
            # API execute response has execution data
            exec_data = resp_json.get("data", {})
            if isinstance(exec_data, dict) and "resultData" in exec_data:
                result_data = exec_data.get("resultData", {})
                # Try to get output from "Step 10: Respond to Webhook" node
                if isinstance(result_data, dict) and "runData" in result_data:
                    run_data = result_data.get("runData", {})
                    if isinstance(run_data, dict):
                        # Find the last executed node's output
                        for node_name, node_output in run_data.items():
                            if isinstance(node_output, list) and node_output:
                                last_output = node_output[-1]
                                if isinstance(last_output, dict) and "data" in last_output:
                                    node_data = last_output.get("data", {})
                                    if isinstance(node_data, dict) and "main" in node_data:
                                        main = node_data.get("main", [[]])
                                        if isinstance(main, list) and main and isinstance(main[0], list):
                                            if main[0]:
                                                out["response_json"] = main[0][0].get("json", {})
                                                return out
        # Fallback: if structured format not found, use as-is
        out["response_json"] = resp_json
    except Exception as e:
        out["_parse_error"] = str(e)
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


def _filter_asset_candidates(candidates: list[dict], cap: int = 120) -> list[dict]:
    """
    Dedupe, remove junk, and cap asset candidates BEFORE building the LLM prompt.
    Mirrors the n8n Code node logic so the prompt_user sees the cleaned list.
    """
    import re
    from urllib.parse import urlparse, urlencode, parse_qs

    JUNK_URL_PATTERNS = [
        r"1x1", r"spacer", r"pixel", r"blank\.", r"tracking",
        r"favicon", r"apple-touch-icon", r"safari-pinned-tab",
        r"wp-emoji", r"gravatar\.com", r"googletagmanager",
        r"facebook\.com/tr", r"analytics", r"beacon",
        r"\.gif$", r"data:image/svg", r"data:image/gif",
        r"cookie", r"gdpr", r"consent",
    ]
    JUNK_URL_RE = [re.compile(p, re.IGNORECASE) for p in JUNK_URL_PATTERNS]

    JUNK_CLS_RE = re.compile(
        r"icon-(?:arrow|chevron|caret|close|menu|search|social)", re.IGNORECASE
    )
    SOCIAL_ALT_RE = re.compile(
        r"^(facebook|twitter|instagram|linkedin|youtube|tiktok|pinterest)\s*(icon|logo)?$",
        re.IGNORECASE,
    )
    TRACKING_PARAMS = {
        "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
        "fbclid", "gclid", "ref", "_ga", "mc_cid", "mc_eid",
    }

    def normalise_url(u: str) -> str:
        try:
            parsed = urlparse(u)
            qs = parse_qs(parsed.query, keep_blank_values=False)
            cleaned_qs = {k: v for k, v in qs.items() if k not in TRACKING_PARAMS}
            new_query = urlencode(cleaned_qs, doseq=True) if cleaned_qs else ""
            frag = "" if parsed.fragment == "" else parsed.fragment
            return parsed._replace(query=new_query, fragment=frag).geturl()
        except Exception:
            return u

    def is_junk(c: dict) -> bool:
        c_url = (c.get("url") or "").lower()
        alt = (c.get("alt") or "").lower()
        cls = (c.get("cls") or "").lower()
        kind = (c.get("kind") or "").lower()

        if c_url.startswith("data:"):
            return True
        if any(p.search(c_url) for p in JUNK_URL_RE):
            return True
        if JUNK_CLS_RE.search(cls):
            return True
        if SOCIAL_ALT_RE.match(alt):
            return True
        if kind == "svg_inline" and not re.search(r"logo|brand|mark", alt + " " + cls, re.IGNORECASE):
            return True
        return False

    seen: set[str] = set()
    cleaned: list[dict] = []
    for c in candidates:
        raw_url = c.get("url")
        if not raw_url or not isinstance(raw_url, str):
            continue
        norm = normalise_url(raw_url)
        if norm in seen:
            continue
        if is_junk(c):
            continue
        seen.add(norm)
        cleaned.append({**c, "url": norm})

    return cleaned[:cap]


def call_n8n_image_hunt(
    *,
    url: str,
    business_summary: dict,
    page_summaries: list[dict],
    tier2_page_summaries: list[dict],
    asset_candidates: list[dict],
    concept: dict | None = None,
    mode: Mode = "TEST",
    webhook_url: Optional[str] = None,
) -> dict:
    """
    POST asset candidates + context to n8n /SMB-image-hunt.
    Returns a visual_pack with curated image URLs matched to ad themes.
    """
    target_url = resolve_n8n_webhook("image_hunt", mode, override_url=webhook_url)
    headers = _tender_headers()

    # Filter and dedupe candidates BEFORE building the prompt so the LLM
    # sees the same cleaned list that gets passed in the structured payload.
    filtered_candidates = _filter_asset_candidates(asset_candidates or [])

    # Format page snippets into a readable text block (same pattern as other workflows)
    all_summaries = list(page_summaries or []) + list(tier2_page_summaries or [])
    snippets_text = ""
    for ps in all_summaries:
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

    # Build optional concept context block for targeted image hunting
    if concept and isinstance(concept, dict):
        concept_context = (
            "\n## Target Poster Concept\n"
            "This image hunt is for a specific poster concept. Prioritise images that best realise "
            "this concept's visual direction (award up to +15pts bonus for direct match to suggested imagery).\n\n"
            f"- Concept name: {concept.get('concept_name', '')}\n"
            f"- Headline: {concept.get('headline', '')}\n"
            f"- Supporting copy: {concept.get('supporting_copy', '')}\n"
            f"- CTA: {concept.get('cta', '')}\n"
            f"- Suggested imagery: {concept.get('image_idea', '')}\n"
            f"- Layout guidance: {concept.get('layout_notes', '')}\n"
        )
        concept_task_line = (
            "\n   - When scoring, apply up to +15pt bonus for images that directly match "
            "the concept's suggested_imagery."
        )
    else:
        concept_context = ""
        concept_task_line = ""

    user_template = _load_prompt("smb_image_hunt_user.txt")
    prompt_user = user_template.format(
        url=url,
        business_summary_json=json.dumps(business_summary or {}, ensure_ascii=False, indent=2),
        page_snippets=snippets_text.strip() if snippets_text.strip() else "(no snippets provided)",
        asset_candidates_json=json.dumps(filtered_candidates, ensure_ascii=False, indent=2),
        asset_count=len(filtered_candidates),
        concept_context=concept_context,
        concept_task_line=concept_task_line,
    )

    payload = {
        "payload_type": "smb_image_hunt",
        "url": url,
        "business_summary": business_summary or {},
        "page_summaries": page_summaries or [],
        "tier2_page_summaries": tier2_page_summaries or [],
        "asset_candidates": filtered_candidates,
        "concept": concept or {},
        "prompt_system": _load_prompt("smb_image_hunt_system.txt"),
        "prompt_user": prompt_user,
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


def call_n8n_generate_ad_concepts(
    *,
    business_summary: dict,
    page_summaries: list[dict],
    homepage_markdown: str,
    image_urls: list[str],
    mode: Mode = "TEST",
    webhook_url: Optional[str] = None,
) -> dict:
    """
    POST page context + images to n8n /SMB-generate-ad-concepts.
    Returns poster concepts generated based on business summary, page content, and selected images.
    """
    target_url = resolve_n8n_webhook("generate_ad_concepts", mode, override_url=webhook_url)
    headers = _tender_headers()

    prompt_system = _load_prompt("smb_generate_ad_concepts_system.txt")
    prompt_user = _load_prompt("smb_generate_ad_concepts_user.txt")

    payload = {
        "prompt_system": prompt_system,
        "prompt_user": prompt_user,
        "business_summary": business_summary or {},
        "homepage_markdown": homepage_markdown or "",
        "page_summaries": page_summaries or [],
        "image_urls": image_urls or [],
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
