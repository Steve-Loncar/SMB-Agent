import streamlit as st

from backend.state import init_state


st.set_page_config(
    page_title="SMB Ad Agent (Alpha)",
    page_icon="🧩",
    layout="wide",
)

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

