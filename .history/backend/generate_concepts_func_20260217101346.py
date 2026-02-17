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

    # Load prompts for generating ad concepts
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
