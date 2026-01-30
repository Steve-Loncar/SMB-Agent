import streamlit as st


st.title("2) Results")

target_url = st.session_state.get("target_url", "")
if not target_url:
    st.warning("No URL provided yet. Go to Home and enter a website URL.")
    st.stop()

st.caption(f"Target: {target_url}")

# --- Placeholder pipeline behaviour (alpha UI) ---
# We'll replace this with: scrape → n8n trigger → model output → render.
status = st.session_state.get("scrape_status", "idle")

with st.sidebar:
    st.subheader("Run status")
    st.write(f"**{status}**")
    if st.button("Reset"):
        st.session_state["target_url"] = ""
        st.session_state["scrape_status"] = "idle"
        st.session_state["business_summary"] = ""
        st.session_state["poster_concepts"] = []
        st.switch_page("pages/01_home.py")


if status in ("idle", "queued"):
    st.info("Alpha placeholder: generating mocked outputs.")

    # Mock outputs for now so the UI is end-to-end.
    st.session_state["business_summary"] = (
        "This business appears to offer products/services aimed at customers who value quality and convenience. "
        "Key differentiators likely include clear benefits, straightforward pricing, and a customer-friendly experience."
    )
    st.session_state["poster_concepts"] = [
        {
            "headline": "Make Your Day Easier",
            "subhead": "Quality you can trust—delivered with simplicity.",
            "cta": "Visit the site",
        },
        {
            "headline": "Upgrade Without the Hassle",
            "subhead": "Fast, friendly, and built for busy people.",
            "cta": "Get started",
        },
        {
            "headline": "Small Business. Big Value.",
            "subhead": "Everything you need—nothing you don't.",
            "cta": "Learn more",
        },
    ]
    st.session_state["scrape_status"] = "done"


st.subheader("Business / product description")
st.write(st.session_state.get("business_summary", ""))

st.divider()

st.subheader("AI-generated poster concepts (text-only for now)")
concepts = st.session_state.get("poster_concepts", [])

if not concepts:
    st.warning("No concepts yet.")
else:
    cols = st.columns(3)
    for i, concept in enumerate(concepts):
        with cols[i % 3]:
            st.markdown("#### Poster concept")
            st.markdown(f"**Headline:** {concept.get('headline','')}")
            st.markdown(f"**Subhead:** {concept.get('subhead','')}")
            st.markdown(f"**CTA:** {concept.get('cta','')}")
            st.button("Generate image (soon)", disabled=True, key=f"gen_{i}")
