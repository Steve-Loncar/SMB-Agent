import streamlit as st
import json
import base64
from backend.n8n_client import (
    call_n8n_generate_ads,
    call_n8n_generate_image,
    call_n8n_scrape_pack,
    resolve_n8n_webhook,
)
from backend.state import initstate

initstate()


st.title("2) Results")

# --- Placeholder pipeline behaviour (alpha UI) ---
# We'll replace this with: scrape → n8n trigger → model output → render.
status = st.session_state.get("scrape_status", "idle")

with st.sidebar:
    st.subheader("n8n")
    # Set index based on current session state value
    current_mode = st.session_state.get("n8n_mode", "TEST")
    mode_index = 0 if current_mode == "TEST" else 1
    mode = st.radio("Mode", ["TEST", "LIVE"], index=mode_index, key="n8n_mode", horizontal=True)
    st.caption(f"Scrape-pack: `{resolve_n8n_webhook('scrape_pack', mode)}`")
    st.caption(f"Ads endpoint: `{resolve_n8n_webhook('generate_ads', mode)}`")
    st.caption(f"Image endpoint: `{resolve_n8n_webhook('generate_image', mode)}`")

    st.subheader("Run status")
    st.write(f"**{status}**")
    st.caption("V2: scrape-pack runs via n8n on page load when queued.")

    # Allow re-running AI without re-scraping (useful for n8n prompt iteration)
    can_run_ai = bool(st.session_state.get("scraped_text"))
    if st.button("Run AI (n8n)", disabled=not can_run_ai):
        with st.spinner("Calling n8n with test payload…"):
            debug_result = call_n8n_generate_ads(
                scraped_text=st.session_state.get("scraped_text", ""),
                image_urls=st.session_state.get("scraped_images", []),
                url=target_url,
                mode=st.session_state.n8n_mode,
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

        mode = st.session_state.n8n_mode
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
        st.session_state["scrape_pack"] = None
        st.session_state["scrape_pack_debug"] = None
        st.session_state["business_summary"] = ""
        st.session_state["poster_concepts"] = []
        st.session_state["poster_images"] = {}
        st.switch_page("pages/01_home.py")

target_url = st.session_state.get("target_url", "")
if not target_url:
    st.warning("No URL provided yet. Go to Home and enter a website URL.")
    st.stop()

st.caption(f"Target: {target_url}")

if status == "queued":
    with st.spinner("Running scrape-pack via n8n…"):
        try:
            debug = call_n8n_scrape_pack(
                url=target_url,
                depth=st.session_state.get("scrape_depth", "homepage_plus"),
                max_pages=int(st.session_state.get("scrape_max_pages", 3)),
                mode=st.session_state.n8n_mode,
            )
            st.session_state["scrape_pack_debug"] = debug

            # If n8n responds with a clean JSON payload, store it as scrape_pack too
            resp_json = debug.get("_n8n_response_json")
            if isinstance(resp_json, list) and resp_json and isinstance(resp_json[0], dict):
                st.session_state["scrape_pack"] = resp_json[0]
            elif isinstance(resp_json, dict):
                st.session_state["scrape_pack"] = resp_json

            st.session_state["scrape_status"] = "scraped"
            st.rerun()
        except Exception as e:
            st.session_state["scrape_status"] = "error"
            st.error(f"scrape-pack failed: {e}")

status = st.session_state.get("scrape_status", "idle")
if status == "error":
    st.stop()

st.subheader("Scrape-pack output (debug)")
sp = st.session_state.get("scrape_pack")
if sp:
    st.json(sp)
else:
    st.info("No scrape-pack payload yet (check debug below).")

dbg = st.session_state.get("scrape_pack_debug")
if dbg:
    with st.expander("Debug: scrape-pack request/response", expanded=False):
        st.write("Target URL:")
        st.code(dbg.get("_debug_target_url", ""), language="text")
        st.write("HTTP status / final URL:")
        st.code(
            f"{dbg.get('_debug_http_status')} | final={dbg.get('_debug_final_url')}",
            language="text",
        )
        if dbg.get("_error"):
            st.error(dbg.get("_error"))
        st.write("Response text (first 400 chars):")
        st.code(dbg.get("_debug_resp_text_snippet", ""), language="text")
        st.write("Payload sent:")
        st.json(dbg.get("_debug_payload_sent", {}))

# NEW: Tiered Scrapepack Viewer (5 lines)
sp = st.session_state.get("scrape_pack")
if sp and isinstance(sp, dict) and "pages" in sp:
    st.subheader("📦 Tiered Signals")
    cols = st.columns(3)
    pages = sp.get("pages", [])
    for i, page in enumerate(pages[:3]):
        with cols[i]:
            tier = page.get("tier", "?")
            page_url = page.get("page_url", "")
            st.metric(f"Tier {tier}", page_url[:40])
            page_signals = page.get("page_signals", {})
            h1_text = page_signals.get("h1", "No h1")
            st.caption(h1_text[:60] if h1_text else "No h1")

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
                        img_res = call_n8n_generate_image(
                            prompt=prompt,
                            mode=st.session_state.n8n_mode,
                        )
                        if not img_res.get("ok"):
                            raise RuntimeError(
                                img_res.get("response_text_snippet", "n8n image call failed")
                            )

                        resp = img_res.get("response_json") or {}
                        # n8n Respond node may return a list (allIncomingItems)
                        if isinstance(resp, list) and resp:
                            resp = resp[0]

                        b64 = (resp or {}).get("image_b64", "")
                        if not b64:
                            raise RuntimeError("Missing image_b64 in n8n response")

                        img_bytes = base64.b64decode(b64)
                    st.session_state["poster_images"][i] = img_bytes
                    st.rerun()
                except Exception as e:
                    st.error(f"Image generation failed: {e}")
