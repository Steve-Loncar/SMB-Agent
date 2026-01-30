import streamlit as st

from backend.scraper import scrape_site
from backend.n8n_client import call_n8n_generate_ads
from backend.state import init_state

init_state()


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
    st.subheader("n8n")
    mode = st.radio("Mode", ["TEST", "LIVE"], key="n8n_mode", horizontal=True)
    if mode == "TEST":
        st.text_input("Test webhook URL", key="n8n_test_url", placeholder="https://fpgconsulting.app.n8n.cloud/webhook-test/generate-ads")
    else:        
        st.text_input("Live webhook URL", key="n8n_live_url", placeholder="https://fpgconsulting.app.n8n.cloud/webhook/generate-ads")

    st.subheader("Run status")
    st.write(f"**{status}**")
    st.caption("Alpha: in-app scrape (will move to n8n later).")
    if st.button("Reset"):
        st.session_state["target_url"] = ""
        st.session_state["scrape_status"] = "idle"
        st.session_state["scraped_text"] = ""
        st.session_state["scraped_images"] = []
        st.session_state["visited_urls"] = []
        st.session_state["business_summary"] = ""
        st.session_state["poster_concepts"] = []
        st.switch_page("pages/01_home.py")

@st.cache_data(show_spinner=False, ttl=60 * 60)
def cached_scrape(url: str):
    # Cache by URL for fast repeats during prompt/UI iteration.
    return scrape_site(url, max_pages=3, max_images_total=12, timeout_s=15)


if status == "queued":
    with st.spinner("Scraping website (alpha)…"):
        try:
            result = cached_scrape(target_url)
            st.session_state["visited_urls"] = result.visited_urls
            st.session_state["scraped_text"] = result.text
            st.session_state["scraped_images"] = result.image_urls

            # Call n8n workflow for AI generation
            with st.spinner("Calling AI workflow (n8n + Sonar)…"):
                mode = st.session_state.get("n8n_mode", "TEST")
                if mode == "LIVE":
                    webhook_url = (st.session_state.get("n8n_live_url") or "").strip()
                else:
                    webhook_url = (st.session_state.get("n8n_test_url") or "").strip()

                if not webhook_url:
                    raise RuntimeError(f"Missing n8n {mode} webhook URL (set it in the sidebar).")

                ai = call_n8n_generate_ads(
                    scraped_text=result.text,
                    image_urls=result.image_urls,
                    url=target_url,
                    webhook_url=webhook_url,
                )

            st.session_state["business_summary"] = ai.get("business_summary", "")
            st.session_state["poster_concepts"] = ai.get("poster_concepts", [])

            st.session_state["scrape_status"] = "done"
        except Exception as e:
            st.session_state["scrape_status"] = "error"
            st.error(f"Scrape failed: {e}")

status = st.session_state.get("scrape_status", "idle")
if status == "error":
    st.stop()

st.subheader("Business / product description")
st.write(st.session_state.get("business_summary", ""))

st.divider()

st.subheader("Scraped pages")
visited = st.session_state.get("visited_urls", [])
if visited:
    st.write(f"Visited {len(visited)} page(s):")
    for u in visited:
        st.write(f"- {u}")
else:
    st.write("No pages scraped yet.")

st.subheader("Scraped text (alpha)")
scraped_text = st.session_state.get("scraped_text", "")
if scraped_text:
    st.text_area("Extracted text", scraped_text, height=240)
else:
    st.write("No text extracted.")

st.subheader("Images found (alpha)")
imgs = st.session_state.get("scraped_images", [])
if imgs:
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
