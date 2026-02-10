import streamlit as st

from backend.state import initstate


st.set_page_config(
    page_title="SMB Ad Agent (Alpha)",
    page_icon="🧩",
    layout="wide",
    initial_sidebar_state="collapsed",
)

initstate()

st.markdown(
    """
    <style>
      /* Hide Streamlit chrome */
      #MainMenu { visibility: hidden; }
      header { visibility: hidden; }
      footer { visibility: hidden; }
      [data-testid="stToolbar"] { display: none; }

      /* Hide default multipage nav in sidebar (we'll use top nav) */
      [data-testid="stSidebarNav"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

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

st.info("Use the top navigation: **Home** → **Results**.", icon="ℹ️")

with st.expander("Dev notes", expanded=False):
    st.write(
        "- This is UI-only for now.\n"
        "- Next: wire scraping + n8n workflow trigger."
    )

