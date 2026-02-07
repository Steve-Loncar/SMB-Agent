import streamlit as st


def init_state() -> None:
    # Core app state
    st.session_state.setdefault("target_url", "")
    st.session_state.setdefault("scrape_status", "idle")  # idle | queued | scraped | done | error
    st.session_state.setdefault("scraped_text", "")
    st.session_state.setdefault("scraped_images", [])
    st.session_state.setdefault("visited_urls", [])
    st.session_state.setdefault("business_summary", "")
    st.session_state.setdefault("poster_concepts", [])
    # Cache generated images by concept index: {0: bytes, 1: bytes, ...}
    st.session_state.setdefault("poster_images", {})

    # n8n settings
    st.session_state.setdefault("n8n_mode", "TEST")  # TEST | LIVE

