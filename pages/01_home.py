import re
import streamlit as st

from backend.state import initstate
from backend.n8n_client import resolve_n8n_webhook

initstate()

with st.sidebar:
    st.subheader("n8n mode")
    st.caption(f"DEBUG HOME: n8n_mode = {st.session_state.get('n8n_mode', 'NOT SET')}")
    st.caption(f"DEBUG HOME: All keys = {list(st.session_state.keys())}")
    mode = st.session_state.get("n8n_mode", "TEST")
    st.caption(f"**{mode}** mode active (change in Results)")
    st.caption(f"Scrape-pack: `{resolve_n8n_webhook('scrape_pack', mode)}`")
    st.caption(f"Generate-ads: `{resolve_n8n_webhook('generate_ads', mode)}`")
    st.caption(f"Generate-image: `{resolve_n8n_webhook('generate_image', mode)}`")

st.title("1) Enter a website URL")
st.caption("Paste the business website you want to analyze.")


def is_probably_valid_url(url: str) -> bool:
    # Very light validation (alpha). We'll harden later.
    if not url:
        return False
    pattern = r"^https?://"
    return re.match(pattern, url.strip()) is not None


url = st.text_input(
    "Website URL",
    placeholder="https://example.com",
    value=st.session_state.get("target_url", ""),
)

# Dev-only controls (for wiring + iteration). You'll hide later.
st.caption("Dev controls (temporary)")
depth = st.selectbox(
    "Scrape depth",
    options=["homepage_only", "homepage_plus"],
    index=1 if st.session_state.get("scrape_depth") == "homepage_plus" else 0,
    help="homepage_plus is intended to fetch homepage plus a couple of likely About/Services pages.",
)
max_pages = st.number_input(
    "Max pages",
    min_value=1,
    max_value=10,
    value=int(st.session_state.get("scrape_max_pages", 3)),
    step=1,
    help="Used by scrape-pack workflow to limit extra internal pages.",
)

col1, col2 = st.columns([1, 3])

with col1:
    apply_clicked = st.button("Apply", type="primary", use_container_width=True)

with col2:
    st.write("")
    st.write("Tip: include `https://` for now.")


if apply_clicked:
    cleaned = url.strip()
    if not is_probably_valid_url(cleaned):
        st.error("Please enter a valid URL starting with http:// or https://")
    else:
        st.session_state["target_url"] = cleaned
        st.session_state["scrape_depth"] = depth
        st.session_state["scrape_max_pages"] = int(max_pages)

        # In the next step we'll kick off scrape + AI generation.
        st.session_state["scrape_status"] = "queued"
        # Clear legacy scrape fields (kept for now, but we stop using them)
        st.session_state["scraped_text"] = ""
        st.session_state["scraped_images"] = []
        st.session_state["visited_urls"] = []

        # Clear V2 scrape-pack fields
        st.session_state["scrape_pack"] = None
        st.session_state["scrape_pack_debug"] = None

        st.session_state["business_summary"] = ""
        st.session_state["poster_concepts"] = []
        st.session_state["poster_images"] = {}
        st.session_state["ads_autorun_done"] = False
        st.session_state["ads_debug"] = None

        st.success("Saved. Opening Results…")
        st.switch_page("pages/02_results.py")


st.divider()

st.subheader("What happens next (placeholder)")
st.markdown(
    """
- We'll scrape the page and subpages for text + images  
- Then generate:
  - a short business/product description  
  - a few advertising poster concepts
"""
)
