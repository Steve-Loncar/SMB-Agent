import streamlit as st
import json
import base64

st.set_page_config(
    page_title="SMB Ad Agent",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from typing import Any
from backend.n8n_client import (
    call_n8n_generate_ads,
    call_n8n_check_text_blobs,
    call_n8n_generate_image,
    call_n8n_scrape_pack,
    resolve_n8n_webhook,
)
from backend.state import initstate

initstate()

# Toggle dev diagnostics (keep plumbing; hide clutter for client demos)
# Flip to True when you're debugging n8n request/response envelopes.
DEBUG_UI = False

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

def _iter_scrape_items(sp):
    """
    Supports both shapes:
      A) {"scrape_pack": [ {page_url, Source, page_signals, page_text_blocks, page_brand, ...}, ... ]}
      B) [ {page_url, Source, ...}, ... ]
    """
    if isinstance(sp, dict) and isinstance(sp.get("scrape_pack"), list):
        return [x for x in sp.get("scrape_pack", []) if isinstance(x, dict)]
    if isinstance(sp, list):
        return [x for x in sp if isinstance(x, dict)]
    return []


def _tier_rank(source: str) -> int:
    s = (source or "").strip().lower()
    order = {"tier0": 0, "homepage": 0, "tier1": 1, "tier2": 2}
    return order.get(s, 99)


def _best_title(sig: dict) -> str:
    if not isinstance(sig, dict):
        return ""
    return (sig.get("h1") or sig.get("title") or "").strip()


def _snippets(blocks: Any, n: int = 2) -> list[str]:
    if not isinstance(blocks, list):
        return []
    out = []
    for b in blocks:
        s = str(b).strip()
        if not s:
            continue
        out.append(s)
        if len(out) >= n:
            break
    return out


def _ranked_pages_for_display(sp: Any, limit: int = 6) -> list[dict]:
    """
    Client-facing shortlist:
    - order by tier: tier0 -> tier1 -> tier2
    - preserve within-tier order from workflow (assumes your Merge append is tier0, tier1, tier2)
    - show title/h1 + 1-2 text snippets
    """
    items = _iter_scrape_items(sp)
    if not items:
        return []

    # stable tier order; preserve original order within tier
    enriched = []
    for it in items:
        src = (it.get("Source") or it.get("source") or "").strip()
        sig = it.get("page_signals") or {}
        blocks = it.get("page_text_blocks") or []
        enriched.append(
            {
                "page_url": (it.get("page_url") or "").strip(),
                "source": src,
                "tier_rank": _tier_rank(src),
                "title": _best_title(sig),
                "snips": _snippets(blocks, n=2),
            }
        )

    enriched.sort(key=lambda x: x["tier_rank"])
    return enriched[:limit]


def _derive_inputs_from_scrape_pack(sp) -> tuple[str, list[str]]:
    """
    Builds bounded (scraped_text, image_urls) for generate-ads from your V2 schema.
    Preference order: tier0/homepage -> tier1 -> tier2 (preserve within-tier order).
    """
    items = _iter_scrape_items(sp)
    if not items:
        return "", []

    order = {"tier0": 0, "homepage": 0, "tier1": 1, "tier2": 2}

    def _rank(it):
        s = (it.get("Source") or it.get("source") or "").strip().lower()
        return order.get(s, 99)

    items = sorted(items, key=_rank)

    parts: list[str] = []
    imgs: list[str] = []

    for it in items:
        url = (it.get("page_url") or "").strip()
        src = (it.get("Source") or it.get("source") or "").strip()

        sig = it.get("page_signals") or {}
        title = (sig.get("title") or "").strip()
        meta = (sig.get("meta_description") or "").strip()
        h1 = (sig.get("h1") or "").strip()

        blocks = it.get("page_text_blocks") or []
        if not isinstance(blocks, list):
            blocks = []
        blocks = [str(b).strip() for b in blocks if str(b).strip()]

        chunk = []
        if src:
            chunk.append(f"SOURCE: {src}")
        if title:
            chunk.append(f"TITLE: {title}")
        if h1:
            chunk.append(f"H1: {h1}")
        if meta:
            chunk.append(f"DESC: {meta}")
        if blocks:
            chunk.append("TEXT:\n" + "\n".join(blocks[:8]))

        if chunk:
            parts.append(f"[PAGE] {url}\n" + "\n".join(chunk))

    scraped_text = "\n\n".join(parts).strip()[:20000]

    # dedupe + cap images
    out_imgs = []
    seen = set()
    for u in imgs:
        if u and u not in seen:
            seen.add(u)
            out_imgs.append(u)
        if len(out_imgs) >= 12:
            break

    return scraped_text, out_imgs


st.title("2) Results")

# --- AI 2nd pass (text blob review) state (kept local; avoids touching backend/state.py) ---
st.session_state.setdefault("check_text_blobs_debug", None)       # debug envelope
st.session_state.setdefault("check_text_blobs_result", None)      # parsed/clean payload (if any)
st.session_state.setdefault("check_text_blobs_autorun_done", False)
st.session_state.setdefault("check_text_blobs_last_url", "")


def _run_check_text_blobs_now(*, target_url: str) -> None:
    """Run the 2nd-pass workflow using the currently loaded scrape_pack (no re-scrape)."""
    sp_local = st.session_state.get("scrape_pack")
    if not sp_local:
        return
    with st.spinner("Running AI 2nd pass (check-text-blobs)…"):
        dbg = call_n8n_check_text_blobs(
            url=target_url,
            scrape_pack=sp_local,
            mode=st.session_state.get("n8n_mode", "TEST"),
        )
    st.session_state["check_text_blobs_debug"] = dbg
    st.session_state["check_text_blobs_last_url"] = target_url
    st.session_state["check_text_blobs_autorun_done"] = True
    st.session_state["check_text_blobs_result"] = dbg.get("_n8n_response_json")

target_url = st.session_state.get("target_url", "")
if not target_url:
    st.warning("No URL provided yet. Go to Home and enter a website URL.")
    st.stop()

st.caption(f"Target: {target_url}")

# --- Client-facing narrative header (lightweight; no new plumbing) ---
status = st.session_state.get("scrape_status", "idle")

st.markdown("### 👋 Thank you — just reviewing your website!")
if status in ("queued", "idle"):
    st.caption("We're doing a quick scan of your homepage and a few key internal pages.")
elif status == "scraped":
    st.caption("Quick check complete — now generating ad concepts based on the most relevant pages.")
elif status == "error":
    st.caption("We hit a snag scanning the site — please try again in a moment.")

sp = st.session_state.get("scrape_pack")
ranked = _ranked_pages_for_display(sp, limit=6)
if ranked and status in ("scraped", "done"):
    st.markdown("#### ✅ Quick check of your website complete")
    st.markdown("These pages look the most relevant:")
    for p in ranked:
        title = p["title"] or "(No headline/title found)"
        tier = (p["source"] or "").upper() or "UNKNOWN"
        st.markdown(f"- **{title}**  \n  {p['page_url']}  \n  _{tier}_")
        for sn in p["snips"]:
            st.caption(f"• {sn[:180]}")
    st.divider()

# --- Placeholder pipeline behaviour (alpha UI) ---
# We'll replace this with: scrape → n8n trigger → model output → render.
status = st.session_state.get("scrape_status", "idle")

with st.sidebar:
    st.subheader("n8n")
    
    # Get current value, default to LIVE if not set
    current_mode = st.session_state.get("n8n_mode", "LIVE")
    current_index = 0 if current_mode == "TEST" else 1
    
    # Radio button with different key, then manually sync
    selected_mode = st.radio("Mode", ["TEST", "LIVE"], index=current_index, key="n8n_mode_widget", horizontal=True)
    
    # Manually update session state
    st.session_state["n8n_mode"] = selected_mode
    mode = selected_mode
    st.caption(f"Scrape-pack: `{resolve_n8n_webhook('scrape_pack', mode)}`")
    st.caption(f"Ads endpoint: `{resolve_n8n_webhook('generate_ads', mode)}`")
    st.caption(f"Image endpoint: `{resolve_n8n_webhook('generate_image', mode)}`")
    st.caption(f"Check text blobs: `{resolve_n8n_webhook('check_text_blobs', mode)}`")

    st.subheader("Run status")
    st.write(f"**{status}**")
    st.caption("V2: scrape-pack runs via n8n on page load when queued.")

    # Allow re-running AI without re-scraping (useful for n8n prompt iteration)
    can_run_ai = bool(st.session_state.get("scraped_text")) or bool(st.session_state.get("scrape_pack"))
    if st.button("Run AI (n8n)", disabled=not can_run_ai):
        # If V2 scrape-pack exists but legacy fields are empty, derive them on-demand
        if not st.session_state.get("scraped_text") and st.session_state.get("scrape_pack"):
            txt, urls = _derive_inputs_from_scrape_pack(st.session_state["scrape_pack"])
            st.session_state["scraped_text"] = txt
            st.session_state["scraped_images"] = urls
        with st.spinner("Calling n8n with test payload…"):
            debug_result = call_n8n_generate_ads(
                scraped_text=st.session_state.get("scraped_text", ""),
                image_urls=st.session_state.get("scraped_images", []),
                url=target_url,
                mode=st.session_state.n8n_mode,
            )
        st.session_state["ads_debug"] = debug_result

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
                        # mark autorun done if this was triggered automatically later
                        st.session_state["ads_autorun_done"] = True
        except Exception:
            # Keep debug visible below; don't crash UI.
            pass

        mode = st.session_state.n8n_mode
        st.success(f"Sent {mode} payload to n8n – check Webhook node Output → JSON.")
        if DEBUG_UI:
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

    # NEW: AI 2nd pass over the already-loaded scrape_pack (no re-scrape required)
    can_run_check = bool(st.session_state.get("scrape_pack"))
    if st.button("Run AI 2nd pass (text blobs)", disabled=not can_run_check):
        _run_check_text_blobs_now(target_url=target_url)
        st.success("2nd pass complete (see Business summary section / diagnostics).")

    if st.button("Reset"):
        st.session_state["target_url"] = ""
        st.session_state["scrape_status"] = "idle"
        st.session_state["scraped_text"] = ""
        st.session_state["scraped_images"] = []
        st.session_state["visited_urls"] = []
        st.session_state["scrape_pack"] = None
        st.session_state["scrape_pack_debug"] = None
        st.session_state["business_summary"] = {}
        st.session_state["poster_concepts"] = []
        st.session_state["check_text_blobs_debug"] = None
        st.session_state["check_text_blobs_result"] = None
        st.session_state["check_text_blobs_autorun_done"] = False
        st.session_state["poster_images"] = {}
        st.session_state["ads_autorun_done"] = False
        st.session_state["ads_debug"] = None
        st.switch_page("pages/01_home.py")

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
            if isinstance(resp_json, list) and resp_json:
                # Two possible shapes:
                #  A) list[page_obj, page_obj, ...]           <-- what your scrape-pack returns
                #  B) list[{ scrape_pack: [...] , ... }]      <-- legacy "allIncomingItems" wrapper
                if (
                    len(resp_json) == 1
                    and isinstance(resp_json[0], dict)
                    and (
                        "scrape_pack" in resp_json[0]
                        or "pages" in resp_json[0]
                    )
                ):
                    st.session_state["scrape_pack"] = resp_json[0]
                else:
                    # Keep the full list so downstream can extract logos across pages
                    st.session_state["scrape_pack"] = resp_json
            elif isinstance(resp_json, dict):
                st.session_state["scrape_pack"] = resp_json

            # ---- Plumbing: hydrate legacy fields from V2 scrape-pack ----
            txt, urls = _derive_inputs_from_scrape_pack(st.session_state.get("scrape_pack"))
            st.session_state["scraped_text"] = txt
            st.session_state["scraped_images"] = urls

            # visited urls (for UI)
            items = _iter_scrape_items(st.session_state.get("scrape_pack"))
            if items:
                st.session_state["visited_urls"] = [
                    x.get("page_url", "") for x in items if x.get("page_url")
                ]

            st.session_state["scrape_status"] = "scraped"

            # OPTIONAL / REQUESTED: run the AI 2nd pass immediately after scrape-pack returns
            # (still allows manual re-run via sidebar button without re-scraping).
            if not st.session_state.get("check_text_blobs_autorun_done", False):
                _run_check_text_blobs_now(target_url=target_url)

            st.rerun()
        except Exception as e:
            st.session_state["scrape_status"] = "error"
            st.error(f"scrape-pack failed: {e}")

status = st.session_state.get("scrape_status", "idle")
if status == "error":
    st.stop()

#
# AUTO-RUN generate-ads ONCE after scrape completes (proof-of-plumbing)
#
if status == "scraped" and not st.session_state.get("ads_autorun_done", False):
    # ensure inputs exist (derive from V2 if needed)
    if not st.session_state.get("scraped_text") and st.session_state.get("scrape_pack"):
        txt, urls = _derive_inputs_from_scrape_pack(st.session_state["scrape_pack"])
        st.session_state["scraped_text"] = txt
        st.session_state["scraped_images"] = urls

    can_autorun = bool(st.session_state.get("scraped_text"))
    if can_autorun:
        with st.spinner("Auto-running generate-ads (n8n)…"):
            debug_result = call_n8n_generate_ads(
                scraped_text=st.session_state.get("scraped_text", ""),
                image_urls=st.session_state.get("scraped_images", []),
                url=target_url,
                mode=st.session_state.get("n8n_mode", "TEST"),
            )
        st.session_state["ads_debug"] = debug_result

        resp_json = debug_result.get("_n8n_response_json")
        try:
            if isinstance(resp_json, list) and resp_json and isinstance(resp_json[0], dict):
                item0 = resp_json[0]
                bs = item0.get("business_summary")
                pc = item0.get("poster_concepts")
                if isinstance(bs, dict):
                    st.session_state["business_summary"] = bs
                if isinstance(pc, list):
                    st.session_state["poster_concepts"] = pc
                    st.session_state["poster_images"] = {}
        except Exception:
            pass

        # prevent infinite rerun loops even if response parsing fails
        st.session_state["ads_autorun_done"] = True
        st.rerun()

if DEBUG_UI:
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

# Keep demo UI clean: only surface 2nd-pass diagnostics in DEBUG_UI
check_dbg = st.session_state.get("check_text_blobs_debug")
if DEBUG_UI and check_dbg:
    with st.expander("Debug: check-text-blobs request/response", expanded=False):
        st.code(check_dbg.get("_debug_target_url", ""), language="text")
        if check_dbg.get("_error"):
            st.error(check_dbg.get("_error"))
        st.json(check_dbg.get("_debug_payload_sent", {}))
        st.json(check_dbg.get("_n8n_response_json", {}))

# Tiered Signals was debug-y; replaced by the client-facing ranked list above.

st.subheader("Business / product description")
bs = st.session_state.get("business_summary", {})
if isinstance(bs, dict) and bs:
    st.markdown(f"**Name:** {bs.get('name_guess','')}")
    st.markdown(f"**Category:** {bs.get('category','')}")
    st.markdown(f"**Value prop:** {bs.get('value_prop','')}")
    st.markdown(f"**Target customer:** {bs.get('target_customer','')}")
    st.markdown(f"**Tone:** {bs.get('tone','')}")
else:
    st.info("Waiting for generate-ads output (auto-runs once after scrape, or use sidebar button).")

# If your new 2nd-pass workflow returns an improved business_summary,
# allow it to overwrite the existing one (without touching poster concepts).
try:
    check_payload = st.session_state.get("check_text_blobs_result")
    if isinstance(check_payload, list) and check_payload and isinstance(check_payload[0], dict):
        maybe_bs = check_payload[0].get("business_summary")
        if isinstance(maybe_bs, dict) and maybe_bs:
            st.session_state["business_summary"] = maybe_bs
except Exception:
    pass

ads_dbg = st.session_state.get("ads_debug")
if DEBUG_UI and ads_dbg:
    with st.expander("Debug: generate-ads request/response", expanded=False):
        st.code(ads_dbg.get("_debug_target_url", ""), language="text")
        if ads_dbg.get("_error"):
            st.error(ads_dbg.get("_error"))
        st.json(ads_dbg.get("_debug_payload_sent", {}))
        st.json(ads_dbg.get("_n8n_response_json", {}))

st.divider()

with st.expander("Developer diagnostics (scrape + requests)", expanded=False):
    # Scrape-pack payload (raw)
    st.subheader("Scrape-pack output (debug)")
    sp = st.session_state.get("scrape_pack")
    if sp:
        st.json(sp)
    else:
        st.info("No scrape-pack payload yet (check debug below).")

    # Scrape-pack request/response debug
    dbg = st.session_state.get("scrape_pack_debug")
    if dbg:
        st.subheader("Debug: scrape-pack request/response")
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

    # Generate-ads request/response debug
    ads_dbg = st.session_state.get("ads_debug")
    if ads_dbg:
        st.subheader("Debug: generate-ads request/response")
        st.code(ads_dbg.get("_debug_target_url", ""), language="text")
        if ads_dbg.get("_error"):
            st.error(ads_dbg.get("_error"))
        st.json(ads_dbg.get("_debug_payload_sent", {}))
        st.json(ads_dbg.get("_n8n_response_json", {}))

    # Scraped pages list (noisy) — now hidden by default
    st.subheader("Scraped pages")
    visited = st.session_state.get("visited_urls", [])
    if visited:
        st.write(f"Visited {len(visited)} page(s):")
        for u in visited:
            st.write(f"- {u}")
    else:
        st.write("No pages scraped yet.")

    # Scraped text (noisy) — now hidden by default
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
