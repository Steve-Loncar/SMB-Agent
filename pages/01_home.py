import re
import streamlit as st

from backend.state import init_state

init_state()

with st.sidebar:
    st.subheader("n8n")
    mode = st.radio("Mode", ["TEST", "LIVE"], key="n8n_mode", horizontal=True)
    if mode == "TEST":
        st.text_input("Test webhook URL", key="n8n_test_url", placeholder="https://fpgconsulting.app.n8n.cloud/webhook-test/generate-ads")
    else:
        st.text_input("Live webhook URL", key="n8n_live_url", placeholder="https://fpgconsulting.app.n8n.cloud/webhook/generate-ads")

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

        # In the next step we'll kick off scrape + AI generation.
        st.session_state["scrape_status"] = "queued"
        st.session_state["scraped_text"] = ""
        st.session_state["scraped_images"] = []
        st.session_state["visited_urls"] = []
        st.session_state["business_summary"] = ""
        st.session_state["poster_concepts"] = []

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
