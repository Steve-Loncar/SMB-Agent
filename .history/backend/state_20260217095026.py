import streamlit as st


def initstate() -> None:
    # Core app state
    st.session_state.setdefault("target_url", "")
    st.session_state.setdefault("scrape_status", "idle")  # idle | queued | scraped | done | error
    # V1 scrape outputs (legacy; will be phased out)
    st.session_state.setdefault("scraped_text", "")
    st.session_state.setdefault("scraped_images", [])
    st.session_state.setdefault("visited_urls", [])

    # V2 scrape-pack config + outputs
    st.session_state.setdefault("scrape_depth", "homepage_plus")   # homepage_only | homepage_plus
    st.session_state.setdefault("scrape_max_pages", 3)
    st.session_state.setdefault("scrape_pack", None)               # clean payload from n8n (if/when)
    st.session_state.setdefault("scrape_pack_debug", None)         # debug envelope returned by backend client
    st.session_state.setdefault("homepage_markdown", "")

    # n8n returns a dict payload here (name_guess, category, etc.)
    st.session_state.setdefault("business_summary", {})
    st.session_state.setdefault("poster_concepts", [])
    # Cache generated images by concept index: {0: bytes, 1: bytes, ...}
    st.session_state.setdefault("poster_images", {})

    # Ads autorun plumbing (Phase 2 bridge)
    st.session_state.setdefault("ads_autorun_done", False)   # only run once per scrape
    st.session_state.setdefault("ads_debug", None)           # store generate-ads debug envelope

    # Image hunt state tracking
    st.session_state.setdefault("image_hunt_done", False)
    st.session_state.setdefault("image_hunt_debug", None)
    st.session_state.setdefault("image_hunt_error", None)
    st.session_state.setdefault("visual_pack", None)
    
    # Carousel state tracking
    st.session_state.setdefault("image_carousel_index", 0)
    st.session_state.setdefault("image_carousel_last_advance", 0)

