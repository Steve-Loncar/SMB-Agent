import os
import requests


def call_n8n_generate_ads(scraped_text: str, image_urls: list[str], url: str, *, webhook_url: str | None = None) -> dict:
    """
    Sends scraped content to an n8n webhook.

    n8n will:
    - call Sonar (Perplexity)
    - return structured JSON
    """

    webhook_url = webhook_url or os.getenv("N8N_WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError("Missing N8N_WEBHOOK_URL environment variable")

    secret = os.getenv("N8N_AGENT_SECRET", "")

    payload = {
        "url": url,
        "scraped_text": scraped_text,
        "image_urls": image_urls,
    }

    headers = {}
    if secret:
        headers["x-agent-secret"] = secret

    r = requests.post(webhook_url, json=payload, headers=headers, timeout=60)
    r.raise_for_status()

    return r.json()
