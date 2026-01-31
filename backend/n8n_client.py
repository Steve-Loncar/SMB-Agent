# backend/n8n_client.py
import requests

def call_n8n_generate_ads(*args, **kwargs) -> dict:
    """
    DEBUG ONLY: ignore inputs and send a fixed JSON payload to the TEST webhook.
    """
    webhook_url = "https://fpgconsulting.app.n8n.cloud/webhook-test/generate-ads"

    payload = {
        "hello": "world-from-streamlit",
        "answer": 42,
        "note": "hardcoded-payload-test"
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    r = requests.post(webhook_url, json=payload, headers=headers, timeout=30)
    # Do NOT try to parse response for now; just return empty dict.
    return {}
