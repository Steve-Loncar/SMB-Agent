import os
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

    n8n will:
    - call Sonar (Perplexity)
    - return structured JSON
    """
    # 1) Decide which URL to hit (Streamlit passes this in)
    webhook_url = webhook_url or os.getenv("N8N_WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError("Missing N8N_WEBHOOK_URL environment variable")

    secret = os.getenv("N8N_AGENT_SECRET", "")

    # 2) Build the payload (TEMP: hello-world debug)
    payload = {
        "hello": "world-from-streamlit",
        "debug_url": url,
        "debug_text_len": len(scraped_text or ""),
        "debug_image_count": len(image_urls or []),
        # later: switch back to real payload:
        # "url": url,
        # "scraped_text": scraped_text,
        # "image_urls": image_urls,
    }

    # 3) Build headers
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if secret:
        headers["x-agent-secret"] = secret

    # 4) Send POST to n8n
    r = requests.post(webhook_url, json=payload, headers=headers, timeout=60)
    r.raise_for_status()

    # 5) Try to parse JSON; if not JSON, raise with body snippet
    try:
        return r.json()
    except Exception:
        body = (r.text or "").strip()
        snippet = body[:800].replace("\n", "\\n")
        raise RuntimeError(
            f"n8n returned non-JSON. status={r.status_code} "
            f"content-type={r.headers.get('content-type')} body={snippet}"
        )
