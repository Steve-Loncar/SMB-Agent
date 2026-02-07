import streamlit as st
import json

from backend.scraper import scrape_site
from backend.n8n_client import call_n8n_generate_ads
from backend.image_gen import generate_poster_image
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

def get_webhook_url() -> str:
    # EXACT Tender-style endpoint construction (no session_state URL storage)
    N8N_BASE_URL = "https://fpgconsulting.app.n8n.cloud"
    N8N_TEST_PATH = "/webhook-test/generate-ads"
    N8N_LIVE_PATH = "/webhook/generate-ads"
    mode = st.session_state.get("n8n_mode", "TEST")
    return (N8N_BASE_URL + N8N_TEST_PATH) if mode == "TEST" else (N8N_BASE_URL + N8N_LIVE_PATH)

def get_image_webhook_url() -> str:
    # Same base + env split, but image endpoint
    N8N_BASE_URL = "https://fpgconsulting.app.n8n.cloud"
    N8N_TEST_PATH = "/webhook-test/generate-image"
    N8N_LIVE_PATH = "/webhook/generate-image"
    mode = st.session_state.get("n8n_mode", "TEST")
    return (N8N_BASE_URL + N8N_TEST_PATH) if mode == "TEST" else (N8N_BASE_URL + N8N_LIVE_PATH)

with st.sidebar:
    st.subheader("n8n")
    st.radio("Mode", ["TEST", "LIVE"], key="n8n_mode", horizontal=True)
    st.caption(f"Ads endpoint: `{get_webhook_url()}`")
    st.caption(f"Image endpoint: `{get_image_webhook_url()}`")

    st.subheader("Run status")
    st.write(f"**{status}**")
    st.caption("Alpha: in-app scrape (will move to n8n later).")

    # Allow re-running AI without re-scraping (useful for n8n prompt iteration)
    can_run_ai = bool(st.session_state.get("scraped_text"))
    if st.button("Run AI (n8n)", disabled=not can_run_ai):
        with st.spinner("Calling n8n with test payload…"):
            debug_result = call_n8n_generate_ads(
                scraped_text=st.session_state.get("scraped_text", ""),
                image_urls=st.session_state.get("scraped_images", []),
                url=target_url,
                webhook_url=get_webhook_url(),
            )

        # ---- NEW: hydrate session_state from n8n response payload ----
        # Your "Respond to Webhook" is set to "allIncomingItems", so expect a list of 1 item.
        resp_json = debug_result.get("_n8n_response_json")
        try:
            if isinstance(resp_json, list) and resp_json:
                item0 = resp_json[0]
                # You are preparing a payload like:
                # { business_summary: {...}, poster_concepts: [...] }
                if isinstance(item0, dict):
                    bs = item0.get("business_summary")
                    pc = item0.get("poster_concepts")
                    if isinstance(bs, dict):
                        st.session_state["business_summary"] = bs
                    if isinstance(pc, list):
                        st.session_state["poster_concepts"] = pc
                        # Reset any previously generated images (concepts changed)
                        st.session_state["poster_images"] = {}
        except Exception:
            # Keep debug visible below; don't crash UI.
            pass

        mode = st.session_state.get("n8n_mode", "TEST")
        st.success(f"Sent {mode} payload to n8n – check Webhook node Output → JSON.")
        with st.expander("Debug: JSON sent to n8n", expanded=True):
            st.write("Target URL:")
            st.code(debug_result.get("_debug_target_url", ""), language="text")
            st.write("HTTP status / final URL:")
            st.code(
                f"{debug_result.get('_debug_http_status')} | final={debug_result.get('_debug_final_url')}",
                language="text",
            )
            if debug_result.get("_error"):
                st.error(debug_result.get("_error"))
            if debug_result.get("_location"):
                st.write("Redirect Location:")
                st.code(debug_result.get("_location", ""), language="text")
            st.write("Response Content-Type:")
            st.code(debug_result.get("_debug_resp_content_type", ""), language="text")
            st.write("Response text (first 400 chars):")
            st.code(debug_result.get("_debug_resp_text_snippet", ""), language="text")
            st.write("n8n response JSON (clean payload):")
            st.json(debug_result.get("_n8n_response_json", {}))
            st.write("Payload:")
            st.json(debug_result.get("_debug_payload_sent", {}))
            st.write("Response headers:")
            st.json(debug_result.get("_debug_resp_headers", {}))
            st.write("Response JSON (parsed):")
            st.json(resp_json)

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
            # Stop here. Let user trigger n8n manually.
            st.session_state["scrape_status"] = "scraped"
            # Ensure the next block runs immediately in this same user flow
            st.rerun()
        except Exception as e:
            st.session_state["scrape_status"] = "error"
            st.error(f"Scrape failed: {e}")

status = st.session_state.get("scrape_status", "idle")
# For this test, we do nothing here. The button above always sends the payload.

status = st.session_state.get("scrape_status", "idle")
if status == "error":
    st.stop()

st.subheader("Business / product description")
bs = st.session_state.get("business_summary", {})
if isinstance(bs, dict) and bs:
    st.markdown(f"**Name:** {bs.get('name_guess','')}")
    st.markdown(f"**Category:** {bs.get('category','')}")
    st.markdown(f"**Value prop:** {bs.get('value_prop','')}")
    st.markdown(f"**Target customer:** {bs.get('target_customer','')}")
    st.markdown(f"**Tone:** {bs.get('tone','')}")
else:
    st.info("Run AI to populate business summary.")

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
    # show first few images inline
    st.caption("Best-effort extraction. We'll improve selection/branding later.")
    st.image(imgs[:6], caption=imgs[:6], use_container_width=True)
else:
    st.write("No images extracted.")

st.divider()

st.subheader("AI-generated poster concepts")
concepts = st.session_state.get("poster_concepts", [])

if not concepts:
    st.warning("No concepts yet.")
else:
    cols = st.columns(3)
    for i, concept in enumerate(concepts):
        with cols[i % 3]:
            st.markdown("#### Poster concept")
            st.caption(concept.get("concept_name", ""))
            st.markdown(f"**Headline:** {concept.get('headline','')}")
            st.markdown(f"**Supporting copy:** {concept.get('supporting_copy','')}")
            st.markdown(f"**CTA:** {concept.get('cta','')}")
            st.markdown(f"**Layout notes:** {concept.get('layout_notes','')}")
            st.markdown(f"**Image idea:** {concept.get('image_idea','')}")
            tags = concept.get("style_tags") or []
            if isinstance(tags, list) and tags:
                st.caption("Style tags: " + ", ".join([str(t) for t in tags]))

            # Show generated image if we have one
            img_cache = st.session_state.get("poster_images", {}) or {}
            if i in img_cache:
                st.image(img_cache[i], use_container_width=True)

            # Generate on demand
            if st.button("Generate image", key=f"gen_{i}", use_container_width=True):
                bs = st.session_state.get("business_summary", {}) or {}
                # V1 prompt: simple + reliable (iterate later)
                prompt = (
                    "Create a UK roadside OOH poster mockup.\n"
                    f"Business: {bs.get('name_guess','')}\n"
                    f"Category: {bs.get('category','')}\n"
                    f"Tone: {bs.get('tone','')}\n"
                    f"Headline text on poster: {concept.get('headline','')}\n"
                    f"Supporting copy on poster: {concept.get('supporting_copy','')}\n"
                    f"CTA on poster: {concept.get('cta','')}\n"
                    f"Visual concept: {concept.get('image_idea','')}\n"
                    f"Layout guidance: {concept.get('layout_notes','')}\n"
                    f"Style tags: {', '.join(tags) if isinstance(tags, list) else ''}\n"
                    "Design requirements:\n"
                    "- Poster is legible from distance\n"
                    "- Large headline, minimal text\n"
                    "- Clean composition, high contrast\n"
                    "- Do NOT include phone numbers unless explicitly provided\n"
                    "- No brand logos unless provided\n"
                )

                try:
                    with st.spinner("Generating image…"):
                        img_bytes = generate_poster_image(prompt=prompt)
                    st.session_state["poster_images"][i] = img_bytes
                    st.rerun()
                except Exception as e:
                    st.error(f"Image generation failed: {e}")
