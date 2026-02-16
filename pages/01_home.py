import re
import streamlit as st

from backend.state import initstate
from backend.n8n_client import resolve_n8n_webhook

st.set_page_config(
    page_title="SMB Ad Agent",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

initstate()

st.markdown(
    """
    <style>
      /* Hide Streamlit chrome */
      #MainMenu { visibility: hidden; }
      footer { visibility: hidden; }
    /* Keep toolbar visible so sidebar toggle stays accessible */
      [data-testid="stDecoration"] { display: none; }

      /* Keep header present so the sidebar collapsedControl remains clickable */
      [data-testid="stHeader"] { background: rgba(0,0,0,0); }
      [data-testid="collapsedControl"] { display: block; }

      /* Hide default multipage nav in sidebar (we'll use top nav) */
      [data-testid="stSidebarNav"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Top navigation (keeps flow out of sidebar)
nav1, nav2, _spacer = st.columns([2, 2, 6])
with nav1:
    if st.button("Home", use_container_width=True):
        st.switch_page("pages/01_home.py")
with nav2:
    if st.button("Results", use_container_width=True):
        st.switch_page("pages/02_results.py")

st.divider()

with st.sidebar:
    st.subheader("n8n mode")
    mode = st.session_state.get("n8n_mode", "LIVE")
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

# n8n mode selector (choose before running)
current_mode = st.session_state.get("n8n_mode", "LIVE")
selected_mode = st.radio(
    "n8n Mode",
    ["TEST", "LIVE"],
    index=0 if current_mode == "TEST" else 1,
    horizontal=True,
    help="Choose TEST or LIVE mode before running workflows.",
)
st.session_state["n8n_mode"] = selected_mode

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

        st.session_state["business_summary"] = {}
        st.session_state["poster_concepts"] = []
        st.session_state["poster_images"] = {}
        st.session_state["ads_autorun_done"] = False
        st.session_state["ads_debug"] = None

        # Pipeline flags (must match Results page Reset button)
        st.session_state["homepage_summarise_done"] = False
        st.session_state["homepage_summarise_debug"] = None
        st.session_state["tier1_summarise_done"] = False
        st.session_state["tier1_summarise_debug"] = None
        st.session_state["tier1_page_summaries"] = []
        st.session_state["tier2_page_summaries"] = []
        st.session_state["tier2_decision"] = {}
        st.session_state["check_text_blobs_autorun_done"] = False
        st.session_state["check_text_blobs_debug"] = None
        st.session_state["check_text_blobs_result"] = None
        st.session_state["scrape_pack_pack"] = None

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
