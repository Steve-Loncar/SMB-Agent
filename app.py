import streamlit as st


st.set_page_config(
    page_title="SMB Ad Agent (Alpha)",
    page_icon="🧩",
    layout="wide",
)


def init_state() -> None:
    st.session_state.setdefault("target_url", "")
    st.session_state.setdefault("scrape_status", "idle")  # idle | queued | done | error
    st.session_state.setdefault("scraped_text", "")
    st.session_state.setdefault("scraped_images", [])
    st.session_state.setdefault("visited_urls", [])
    st.session_state.setdefault("business_summary", "")
    st.session_state.setdefault("poster_concepts", [])


init_state()

st.title("🧩 SMB Ad Agent (Alpha)")
st.caption(
    "Basic alpha UI. Enter a business website, then review a generated description and ad poster concepts."
)

st.markdown(
    """
### How it works (alpha)
1. Paste a website URL
2. Click **Apply**
3. Review the output on the Results page
"""
)

st.info("Use the sidebar to navigate: **Home** → **Results**.", icon="ℹ️")

with st.expander("Dev notes", expanded=False):
    st.write(
        "- This is UI-only for now.\n"
        "- Next: wire scraping + n8n workflow trigger."
    )
