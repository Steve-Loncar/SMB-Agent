import streamlit as st
import json
import base64

st.set_page_config(
    page_title="SMB Ad Agent",
    page_icon="S",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from typing import Any
from backend.n8n_client import (
    call_n8n_generate_ads,
    call_n8n_check_text_blobs,
    call_n8n_generate_image,
    call_n8n_scrape_pack,
    call_n8n_homepage_summarise,
    call_n8n_tier1_summarise,
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


def _extract_urls_by_tier(scrape_pack_payload) -> dict[int, list[str]]:
    """Return tier -> ordered unique URLs based on Source field within each tier."""
    tiers: dict[int, list[str]] = {0: [], 1: [], 2: []}
    seen: dict[int, set[str]] = {0: set(), 1: set(), 2: set()}
    for item in _iter_scrape_items(scrape_pack_payload):
        url = (item.get("page_url") or "").strip()
        src = (item.get("Source") or item.get("source") or "").strip().lower()
        tier = {"tier0": 0, "homepage": 0, "tier1": 1, "tier2": 2}.get(src, 99)
        if tier not in tiers:
            tiers[tier] = []
            seen[tier] = set()
        if url and url not in seen[tier]:
            tiers[tier].append(url)
            seen[tier].add(url)
    # Ensure keys exist even if empty
    for t in (0, 1, 2):
        tiers.setdefault(t, [])
    return tiers


def _extract_homepage_markdown(scrape_pack_payload) -> str:
    """Best-effort extraction of homepage markdown from tier 0 scrape result."""
    for item in _iter_scrape_items(scrape_pack_payload):
        src = (item.get("Source") or item.get("source") or "").strip().lower()
        if src in ("tier0", "homepage"):
            md = item.get("markdown") or item.get("md") or item.get("content") or item.get("homepage_markdown") or item.get("page_markdown")
            if isinstance(md, str) and md.strip():
                return md.strip()
    return ""


def _extract_pack_summary(sp: Any) -> dict:
    """
    Prefer the NEW, simple Set-node shape:
      {
        "homepage_url": str,
        "tier1_urls": [str, ...],
        "tier2_urls": [str, ...],
        "homepage_markdown": str
      }

    Back-compat:
      - If sp is a list/dict of page items, infer tiers from Source + page_url.
      - Try to find homepage markdown from tier0/homepage item keys.
    """
    # --- New shape (recommended) ---
    if isinstance(sp, dict):
        has_new = (
            isinstance(sp.get("homepage_url"), str)
            and isinstance(sp.get("tier1_urls"), list)
            and isinstance(sp.get("tier2_urls"), list)
        )
        if has_new:
            return {
                "homepage_url": (sp.get("homepage_url") or "").strip(),
                "tier1_urls": [str(u).strip() for u in (sp.get("tier1_urls") or []) if str(u).strip()],
                "tier2_urls": [str(u).strip() for u in (sp.get("tier2_urls") or []) if str(u).strip()],
                "homepage_markdown": (sp.get("homepage_markdown") or "").strip(),
            }

    # --- Old shape fallback ---
    items = _iter_scrape_items(sp)
    homepage_url = ""
    tier1_urls: list[str] = []
    tier2_urls: list[str] = []
    homepage_markdown = ""

    for it in items:
        url = (it.get("page_url") or "").strip()
        src = (it.get("Source") or it.get("source") or "").strip().lower()
        if not url:
            continue

        if src in ("tier0", "homepage"):
            if not homepage_url:
                homepage_url = url
            # try likely markdown keys (adjust if your workflow uses different names)
            homepage_markdown = (
                (it.get("homepage_markdown") or "")
                or (it.get("page_markdown") or "")
                or (it.get("markdown") or "")
                or ""
            ).strip()
        elif src == "tier1":
            tier1_urls.append(url)
        elif src == "tier2":
            tier2_urls.append(url)

    # de-dupe, preserve order
    def _dedupe(seq: list[str]) -> list[str]:
        seen = set()
        out = []
        for u in seq:
            if u and u not in seen:
                seen.add(u)
                out.append(u)
        return out

    return {
        "homepage_url": homepage_url,
        "tier1_urls": _dedupe(tier1_urls),
        "tier2_urls": _dedupe(tier2_urls),
        "homepage_markdown": homepage_markdown,
    }


def _derive_inputs_from_scrape_pack(sp) -> tuple[str, list[str]]:
    """
    Builds bounded (scraped_text, image_urls) for generate-ads from your V2 schema.
    Preference order: tier0/homepage -> tier1 -> tier2 (preserve within-tier order).

    Also handles the NEW Set-node shape where sp is a flat dict with
    homepage_url, tier1_urls, tier2_urls, homepage_markdown (no page items).
    """
    # --- NEW shape: flat summary dict from Set node ---
    if isinstance(sp, dict) and "homepage_url" in sp and "tier1_urls" in sp:
        parts: list[str] = []
        hp_url = (sp.get("homepage_url") or "").strip()
        hp_md = (sp.get("homepage_markdown") or "").strip()
        if hp_url or hp_md:
            chunk = f"[PAGE] {hp_url}\nSOURCE: homepage"
            if hp_md:
                chunk += f"\nTEXT:\n{hp_md[:12000]}"
            parts.append(chunk)
        for label, key in [("tier1", "tier1_urls"), ("tier2", "tier2_urls")]:
            for u in (sp.get(key) or []):
                u = str(u).strip()
                if u:
                    parts.append(f"[PAGE] {u}\nSOURCE: {label}")
        scraped_text = "\n\n".join(parts).strip()[:20000]
        return scraped_text, []

    # --- OLD shape: list of page-item dicts ---
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


st.title("Results")

# --- AI 2nd pass (text blob review) state (kept local; avoids touching backend/state.py) ---
st.session_state.setdefault("check_text_blobs_debug", None)       # debug envelope
st.session_state.setdefault("check_text_blobs_result", None)      # parsed/clean payload (if any)
st.session_state.setdefault("check_text_blobs_autorun_done", False)
st.session_state.setdefault("check_text_blobs_last_url", "")

# Homepage summarise + tier 1 summarise pipeline state
st.session_state.setdefault("homepage_summarise_done", False)
st.session_state.setdefault("homepage_summarise_debug", None)
st.session_state.setdefault("tier1_summarise_done", False)
st.session_state.setdefault("tier1_summarise_debug", None)
st.session_state.setdefault("tier1_page_summaries", [])


def _run_check_text_blobs_now(*, target_url: str) -> None:
    """Run the 2nd-pass workflow using the currently loaded scrape_pack (no re-scrape)."""
    sp_local = st.session_state.get("scrape_pack")
    if not sp_local:
        return
    with st.spinner("Analysing content..."):
        dbg = call_n8n_check_text_blobs(
            url=target_url,
            scrape_pack=sp_local,
            mode=st.session_state.get("n8n_mode", "TEST"),
        )
    st.session_state["check_text_blobs_debug"] = dbg
    st.session_state["check_text_blobs_last_url"] = target_url
    st.session_state["check_text_blobs_autorun_done"] = True
    st.session_state["check_text_blobs_result"] = dbg.get("_n8n_response_json")

# --- Sidebar (always visible, even without URL) ---
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
    st.caption(f"Homepage summarise: `{resolve_n8n_webhook('homepage_summarise', mode)}`")
    st.caption(f"Tier 1 summarise: `{resolve_n8n_webhook('tier1_summarise', mode)}`")

    st.subheader("Run status")
    st.write(f"**{status}**")
    st.caption("V2: scrape-pack runs via n8n on page load when queued.")

    # Allow re-running AI without re-scraping (useful for n8n prompt iteration)
    can_run_ai = bool(st.session_state.get("scraped_text")) or bool(st.session_state.get("scrape_pack"))
    if st.button("Run AI (n8n)", disabled=not can_run_ai):
        target_url = st.session_state.get("target_url", "")
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
        target_url = st.session_state.get("target_url", "")
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
        st.session_state["homepage_summarise_done"] = False
        st.session_state["homepage_summarise_debug"] = None
        st.session_state["tier1_summarise_done"] = False
        st.session_state["tier1_summarise_debug"] = None
        st.session_state["tier1_page_summaries"] = []
        st.switch_page("pages/01_home.py")

target_url = st.session_state.get("target_url", "")
if not target_url:
    st.warning("No URL provided yet. Go to Home and enter a website URL.")
    st.stop()

# --- Client-facing narrative header ---
status = st.session_state.get("scrape_status", "idle")

st.markdown("### Thank you — we're reviewing your website")
if status in ("queued", "idle"):
    st.caption("Scanning your homepage and key internal pages.")
elif status == "scraped":
    st.caption("Scan complete — now analysing your homepage.")
elif status == "summarising":
    st.caption("Analysing your homepage...")
elif status == "analysing_pages":
    st.caption("Reviewing key pages for advertising material...")
elif status == "generating_ads":
    st.caption("Creating your campaign concepts...")
elif status == "done":
    st.caption("All done. Here are your results.")
elif status == "error":
    st.caption("Something went wrong scanning the site. Please try again shortly.")

sp = st.session_state.get("scrape_pack")
pack = _extract_pack_summary(sp or {})
tiers = {
    0: [pack.get("homepage_url", "")] if pack.get("homepage_url") else [],
    1: pack.get("tier1_urls", []) or [],
    2: pack.get("tier2_urls", []) or [],
}
homepage_md = pack.get("homepage_markdown", "") or ""

# Persist a clean "pack" for downstream steps (summariser, snippet mining, concept gen, etc.)
if sp and not st.session_state.get("scrape_pack_pack"):
    st.session_state["scrape_pack_pack"] = {
        "input_url": target_url,
        "tiers": tiers,
        "homepage_markdown": homepage_md,
        "raw": sp,
    }

if (tiers.get(1) or tiers.get(2)) and status in ("scraped", "summarising", "analysing_pages", "generating_ads", "done"):
    st.markdown("#### Website scan complete")
    st.caption("Pages we identified as most relevant to your advertising:")

    _card_css = """
    <style>
    .tier-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px;
        padding: 1rem 1.2rem;
        max-height: 280px;
        overflow-y: auto;
        margin-bottom: 0.5rem;
    }
    .tier-card p { margin: 0.25rem 0; font-size: 0.88rem; line-height: 1.5; }
    .tier-label { font-weight: 600; margin-bottom: 0.5rem; font-size: 0.78rem;
                  text-transform: uppercase; letter-spacing: 0.04em; opacity: 0.6; }
    </style>
    """
    st.markdown(_card_css, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        # Homepage first, then tier 1
        key_pages = tiers.get(0, []) + tiers.get(1, [])
        t1_links = "".join(f'<p><a href="{u}" target="_blank">{u}</a></p>' for u in key_pages)
        st.markdown(
            f'<div class="tier-card"><div class="tier-label">Key pages</div>{t1_links or "<p>None identified.</p>"}</div>',
            unsafe_allow_html=True,
        )

    with c2:
        t2_links = "".join(f'<p><a href="{u}" target="_blank">{u}</a></p>' for u in tiers.get(2, []))
        st.markdown(
            f'<div class="tier-card"><div class="tier-label">Supporting pages</div>{t2_links or "<p>None identified.</p>"}</div>',
            unsafe_allow_html=True,
        )

    # homepage_md kept in session state for downstream; not shown to client
    st.divider()

if status == "queued":
    with st.spinner("Scanning your website — this may take a moment..."):
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
                # Three possible shapes:
                #  A) list[page_obj, page_obj, ...]   (old scrape-pack)
                #  B) list[{ scrape_pack:[...]}]      (legacy wrapper)
                #  C) list[{ homepage_url, tier1_urls, tier2_urls, homepage_markdown, ... }] (NEW Set-node payload)
                if len(resp_json) == 1 and isinstance(resp_json[0], dict):
                    item0 = resp_json[0]
                    if (
                        "homepage_url" in item0
                        and "tier1_urls" in item0
                        and "tier2_urls" in item0
                    ):
                        st.session_state["scrape_pack"] = item0
                    elif ("scrape_pack" in item0) or ("pages" in item0):
                        st.session_state["scrape_pack"] = item0
                    else:
                        st.session_state["scrape_pack"] = resp_json
                else:
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
            st.error(f"We couldn't scan that website. Please check the URL and try again. ({e})")

status = st.session_state.get("scrape_status", "idle")
if status == "error":
    st.stop()

#
# AUTO-RUN pipeline: homepage-summarise → tier1-summarise → generate-ads
#

# Step 1: Homepage summarise
if status == "scraped" and not st.session_state.get("homepage_summarise_done", False):
    st.session_state["scrape_status"] = "summarising"

    with st.spinner("Building a first-draft summary of your business..."):
        hp_debug = call_n8n_homepage_summarise(
            url=target_url,
            homepage_markdown=homepage_md,
            mode=st.session_state.get("n8n_mode", "TEST"),
        )
    st.session_state["homepage_summarise_debug"] = hp_debug

    # Hydrate business_summary from response
    resp_json = hp_debug.get("_n8n_response_json")
    try:
        # n8n respondWith allIncomingItems wraps in a list
        if isinstance(resp_json, list) and resp_json and isinstance(resp_json[0], dict):
            resp_json = resp_json[0]
        if isinstance(resp_json, dict):
            bs = resp_json.get("business_summary")
            if isinstance(bs, dict):
                st.session_state["business_summary"] = bs
    except Exception:
        pass

    st.session_state["homepage_summarise_done"] = True
    st.rerun()

# Step 2: Tier 1 summarise
status = st.session_state.get("scrape_status", "idle")
if status == "summarising" and not st.session_state.get("tier1_summarise_done", False):
    st.session_state["scrape_status"] = "analysing_pages"

    tier1_urls = pack.get("tier1_urls", []) or []
    bs = st.session_state.get("business_summary", {}) or {}

    with st.spinner("Reviewing your key pages for advertising material..."):
        t1_debug = call_n8n_tier1_summarise(
            url=target_url,
            tier1_urls=tier1_urls,
            business_summary=bs,
            mode=st.session_state.get("n8n_mode", "TEST"),
        )
    st.session_state["tier1_summarise_debug"] = t1_debug

    # Hydrate tier1_page_summaries from response
    resp_json = t1_debug.get("_n8n_response_json")
    try:
        if isinstance(resp_json, list) and resp_json and isinstance(resp_json[0], dict):
            resp_json = resp_json[0]
        if isinstance(resp_json, dict):
            ps = resp_json.get("page_summaries")
            if isinstance(ps, list):
                st.session_state["tier1_page_summaries"] = ps
    except Exception:
        pass

    st.session_state["tier1_summarise_done"] = True
    st.rerun()

# Step 3: Generate ads (chains after tier1 summarise)
status = st.session_state.get("scrape_status", "idle")
if status == "analysing_pages" and not st.session_state.get("ads_autorun_done", False):
    st.session_state["scrape_status"] = "generating_ads"

    # ensure inputs exist (derive from V2 if needed)
    if not st.session_state.get("scraped_text") and st.session_state.get("scrape_pack"):
        txt, urls = _derive_inputs_from_scrape_pack(st.session_state["scrape_pack"])
        st.session_state["scraped_text"] = txt
        st.session_state["scraped_images"] = urls

    can_autorun = bool(st.session_state.get("scraped_text"))
    if can_autorun:
        with st.spinner("Creating your campaign concepts..."):
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
        st.session_state["scrape_status"] = "done"
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

st.subheader("About your business")
bs = st.session_state.get("business_summary", {})
if isinstance(bs, dict) and bs:
    st.caption("From a quick scan of your homepage, here is a first-draft summary:")
    st.markdown(f"**Name:** {bs.get('name_guess','')}")
    st.markdown(f"**Category:** {bs.get('category','')}")
    st.markdown(f"**Value prop:** {bs.get('value_prop','')}")
    st.markdown(f"**Target customer:** {bs.get('target_customer','')}")
    st.markdown(f"**Tone:** {bs.get('tone','')}")
else:
    st.info("We're still working on this. It will appear here shortly.")

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

# --- Key page highlights (tier 1 summaries) ---
_page_summaries = st.session_state.get("tier1_page_summaries", [])
if isinstance(_page_summaries, list) and _page_summaries:
    st.divider()
    st.subheader("Key page highlights")
    st.caption("The most relevant advertising material from your key pages:")

    _highlight_css = """
    <style>
    .highlight-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.75rem;
    }
    .highlight-card .page-title { font-weight: 600; font-size: 0.95rem; margin-bottom: 0.25rem; }
    .highlight-card .page-url { font-size: 0.78rem; opacity: 0.5; margin-bottom: 0.5rem; }
    .highlight-card .page-url a { color: inherit; text-decoration: none; }
    .highlight-card ul { margin: 0; padding-left: 1.2rem; }
    .highlight-card li { font-size: 0.88rem; line-height: 1.6; margin-bottom: 0.15rem; }
    </style>
    """
    st.markdown(_highlight_css, unsafe_allow_html=True)

    for ps in _page_summaries:
        if not isinstance(ps, dict):
            continue
        p_title = ps.get("page_title", "")
        p_url = ps.get("page_url", "")
        snippets = ps.get("ad_snippets", [])
        if not isinstance(snippets, list):
            snippets = []

        snippet_html = "".join(f"<li>{s}</li>" for s in snippets if isinstance(s, str) and s.strip())
        card_html = (
            f'<div class="highlight-card">'
            f'<div class="page-title">{p_title}</div>'
            f'<div class="page-url"><a href="{p_url}" target="_blank">{p_url}</a></div>'
            f'<ul>{snippet_html or "<li>No snippets extracted.</li>"}</ul>'
            f'</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)

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

# Images section — hidden when empty (no "alpha" label for clients)
imgs = st.session_state.get("scraped_images", [])
if imgs:
    st.subheader("Images from your website")
    st.image(imgs[:6], caption=imgs[:6], use_container_width=True)

st.divider()

st.subheader("Campaign concepts")
concepts = st.session_state.get("poster_concepts", [])

if not concepts:
    st.info("Concepts will appear here once generation is complete.")
else:
    cols = st.columns(3)
    for i, concept in enumerate(concepts):
        with cols[i % 3]:
            st.markdown("#### Concept")
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
                    with st.spinner("Generating visual..."):
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
