import os
import streamlit as st


def init_state() -> None:
    # Core app state
    st.session_state.setdefault("target_url", "")
    st.session_state.setdefault("scrape_status", "idle")  # idle | queued | done | error
    st.session_state.setdefault("scraped_text", "")
    st.session_state.setdefault("scraped_images", [])
    st.session_state.setdefault("visited_urls", [])
    st.session_state.setdefault("business_summary", "")
    st.session_state.setdefault("poster_concepts", [])

    # n8n settings
    st.session_state.setdefault("n8n_mode", "TEST")  # TEST | LIVE
    # Hardcode for alpha iteration (you can move these to Secrets later)
    st.session_state.setdefault(
        "n8n_test_url",
        os.getenv("N8N_TEST_WEBHOOK_URL", "PASTE_YOUR_WEBHOOK_TEST_URL_HERE"),
    )
    st.session_state.setdefault(
        "n8n_live_url",
        os.getenv("N8N_WEBHOOK_URL", "PASTE_YOUR_WEBHOOK_LIVE_URL_HERE"),
    )
