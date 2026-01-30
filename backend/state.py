import os
import streamlit as st

# n8n endpoints (mirror tender_agent_app pattern)
N8N_BASE_URL = "https://fpgconsulting.app.n8n.cloud"
# IMPORTANT: set this to the Webhook node "Path" in n8n
N8N_WEBHOOK_NAME = "generate-ads"
N8N_TEST_PATH = f"/webhook-test/{N8N_WEBHOOK_NAME}"
N8N_LIVE_PATH = f"/webhook/{N8N_WEBHOOK_NAME}"


def init_state() -> None:
    # Core app state
    st.session_state.setdefault("target_url", "")
    st.session_state.setdefault("scrape_status", "idle")  # idle | queued | scraped | done | error
    st.session_state.setdefault("scraped_text", "")
    st.session_state.setdefault("scraped_images", [])
    st.session_state.setdefault("visited_urls", [])
    st.session_state.setdefault("business_summary", "")
    st.session_state.setdefault("poster_concepts", [])

    # n8n settings
    st.session_state.setdefault("n8n_mode", "TEST")  # TEST | LIVE
    # Computed URLs (no paste boxes) - always set to avoid stale/empty session values
    st.session_state["n8n_test_url"] = N8N_BASE_URL + N8N_TEST_PATH
    st.session_state["n8n_live_url"] = N8N_BASE_URL + N8N_LIVE_PATH

