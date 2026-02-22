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
    call_n8n_generate_poster,
    call_n8n_image_hunt,
    call_n8n_generate_ad_concepts,
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
st.session_state.setdefault("tier2_page_summaries", [])
st.session_state.setdefault("tier2_decision", {})
st.session_state.setdefault("asset_candidates", [])

# Image generation request plumbing (prevents missed clicks / double submits)
st.session_state.setdefault("generate_image_pending", False)
st.session_state.setdefault("generate_image_request", None)  # {"concept_index": int, "concept": dict, "guidelines": dict, "image_urls": list}
st.session_state.setdefault("generate_image_error", None)

st.session_state.setdefault("image_hunt_done", False)
st.session_state.setdefault("image_hunt_debug", None)
st.session_state.setdefault("visual_pack", None)

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
    # ── n8n mode ──────────────────────────────────────────────────────────────
    st.subheader("n8n Mode")

    current_mode = st.session_state.get("n8n_mode", "LIVE")
    current_index = 0 if current_mode == "TEST" else 1
    selected_mode = st.radio("Webhook mode", ["TEST", "LIVE"], index=current_index, key="n8n_mode_widget", horizontal=True)
    st.session_state["n8n_mode"] = selected_mode
    mode = selected_mode

    with st.expander("Endpoints", expanded=False):
        st.caption(f"Scrape-pack: `{resolve_n8n_webhook('scrape_pack', mode)}`")
        st.caption(f"Tier 1 summarise: `{resolve_n8n_webhook('tier1_summarise', mode)}`")
        st.caption(f"Homepage summarise: `{resolve_n8n_webhook('homepage_summarise', mode)}`")
        st.caption(f"Generate concepts: `{resolve_n8n_webhook('generate_ads', mode)}`")
        st.caption(f"Image hunt: `{resolve_n8n_webhook('image_hunt', mode)}`")
        st.caption(f"Generate poster: `{resolve_n8n_webhook('generate_poster', mode)}`")
        st.caption(f"Generate image: `{resolve_n8n_webhook('generate_image', mode)}`")
        st.caption(f"Check text blobs: `{resolve_n8n_webhook('check_text_blobs', mode)}`")

    # ── Pipeline status ────────────────────────────────────────────────────────
    st.subheader("Pipeline Status")
    _s = st.session_state.get("scrape_status", "idle")
    _t1_done = st.session_state.get("tier1_summarise_done", False)
    _hp_done = st.session_state.get("homepage_summarise_done", False)
    _ads_done = st.session_state.get("ads_autorun_done", False)
    _concepts = st.session_state.get("poster_concepts", [])
    st.markdown(
        f"{'✅' if _s not in ('idle','queued') else '⏳'} **Scrape** `{_s}`  \n"
        f"{'✅' if _t1_done else '⏳'} Page analysis  \n"
        f"{'✅' if _hp_done else '⏳'} Business summary  \n"
        f"{'✅' if _concepts else ('⏳' if not _ads_done else '⚠️')} Concepts "
        f"({'none returned' if _ads_done and not _concepts else f'{len(_concepts)} ready' if _concepts else 'pending'})"
    )

    # ── Manual pipeline controls ───────────────────────────────────────────────
    st.subheader("Manual Controls")

    _has_pack = bool(st.session_state.get("scrape_pack"))
    _has_t1 = bool(st.session_state.get("tier1_page_summaries"))
    _has_bs = bool(st.session_state.get("business_summary"))

    # Step 1: Re-run page analysis (tier1 summarise)
    if st.button("① Re-run Page Analysis", disabled=not _has_pack, use_container_width=True):
        _t1_url = st.session_state.get("target_url", "")
        _sp = st.session_state.get("scrape_pack", {}) or {}
        _t1_urls = _sp.get("tier1_urls", []) if isinstance(_sp, dict) else []
        _t2_urls = _sp.get("tier2_urls", []) if isinstance(_sp, dict) else []
        with st.spinner("Analysing pages…"):
            _t1_dbg = call_n8n_tier1_summarise(
                url=_t1_url,
                tier1_urls=_t1_urls,
                tier2_urls=_t2_urls,
                business_summary=st.session_state.get("business_summary", {}),
                mode=mode,
            )
        _t1_resp = _t1_dbg.get("_n8n_response_json")
        if isinstance(_t1_resp, list) and _t1_resp:
            _t1_resp = _t1_resp[0]
        if isinstance(_t1_resp, dict):
            if isinstance(_t1_resp.get("page_summaries"), list):
                st.session_state["tier1_page_summaries"] = _t1_resp["page_summaries"]
            if isinstance(_t1_resp.get("asset_candidates"), list):
                st.session_state["asset_candidates"] = _t1_resp["asset_candidates"]
        st.session_state["tier1_summarise_done"] = True
        # reset downstream so they re-run
        st.session_state["homepage_summarise_done"] = False
        st.session_state["ads_autorun_done"] = False
        st.session_state["poster_concepts"] = []
        st.success("Page analysis complete.")
        st.rerun()

    # Step 2: Re-run business summary (homepage summarise)
    if st.button("② Re-run Business Summary", disabled=not _has_pack, use_container_width=True):
        _hp_url = st.session_state.get("target_url", "")
        _hp_md = st.session_state.get("homepage_markdown", "") or ""
        _all_snips = list(st.session_state.get("tier1_page_summaries", []) or [])
        _all_snips += list(st.session_state.get("tier2_page_summaries", []) or [])
        with st.spinner("Building business summary…"):
            _hp_dbg = call_n8n_homepage_summarise(
                url=_hp_url,
                homepage_markdown=_hp_md,
                page_summaries=_all_snips,
                mode=mode,
            )
        _hp_resp = _hp_dbg.get("_n8n_response_json")
        if isinstance(_hp_resp, list) and _hp_resp:
            _hp_resp = _hp_resp[0]
        if isinstance(_hp_resp, dict) and isinstance(_hp_resp.get("business_summary"), dict):
            st.session_state["business_summary"] = _hp_resp["business_summary"]
        st.session_state["homepage_summarise_done"] = True
        # reset downstream
        st.session_state["ads_autorun_done"] = False
        st.session_state["poster_concepts"] = []
        st.success("Business summary updated.")
        st.rerun()

    # Step 3: Generate concepts
    can_run_concepts = bool(st.session_state.get("scraped_text")) or _has_pack
    if st.button("③ Generate Concepts", disabled=not can_run_concepts, use_container_width=True):
        _gc_url = st.session_state.get("target_url", "")
        if not st.session_state.get("scraped_text") and _has_pack:
            _txt, _urls = _derive_inputs_from_scrape_pack(st.session_state["scrape_pack"])
            st.session_state["scraped_text"] = _txt
            st.session_state["scraped_images"] = _urls
        _gc_hp_md = st.session_state.get("homepage_markdown", "") or ""
        _sp2 = st.session_state.get("scrape_pack")
        if not _gc_hp_md and isinstance(_sp2, dict):
            _gc_hp_md = _sp2.get("homepage_markdown", "") or ""
        _all_ps = list(st.session_state.get("tier1_page_summaries", []) or [])
        _all_ps += list(st.session_state.get("tier2_page_summaries", []) or [])
        
        # Extract image URLs if visual_pack exists (from image hunt)
        _image_urls = []
        _vp = st.session_state.get("visual_pack") or {}
        if isinstance(_vp, dict):
            _vp_imgs = _vp.get("images", [])
            if isinstance(_vp_imgs, list):
                _image_urls = [img.get("url") for img in _vp_imgs if isinstance(img, dict) and img.get("url")]
        
        # If no visual_pack, fall back to scraped images
        if not _image_urls:
            _image_urls = st.session_state.get("scraped_images", [])
        
        with st.spinner("Generating campaign concepts…"):
            _gc_dbg = call_n8n_generate_ad_concepts(
                business_summary=st.session_state.get("business_summary", {}),
                page_summaries=_all_ps,
                homepage_markdown=_gc_hp_md,
                image_urls=_image_urls,
                mode=mode,
            )
        st.session_state["concepts_debug"] = _gc_dbg
        _gc_resp = _gc_dbg.get("_n8n_response_json")
        try:
            if isinstance(_gc_resp, list) and _gc_resp:
                _gc_resp = _gc_resp[0]
            if isinstance(_gc_resp, dict):
                _pc2 = _gc_resp.get("poster_concepts")
                if isinstance(_pc2, list):
                    st.session_state["poster_concepts"] = _pc2
                    st.session_state["poster_images"] = {}
                    st.session_state["concept_visual_packs"] = {}
        except Exception:
            pass
        st.session_state["ads_autorun_done"] = True
        if st.session_state.get("poster_concepts"):
            st.success(f"Generated {len(st.session_state['poster_concepts'])} concepts.")
        else:
            st.error("No concepts returned — check n8n execution / response schema.")
        st.rerun()

    # Step 4: Global image hunt (for testing / sidebar use)
    can_run_image_hunt = bool(st.session_state.get("asset_candidates"))
    if st.button("④ Global Image Hunt", disabled=not can_run_image_hunt, use_container_width=True):
        _ih_url = st.session_state.get("target_url", "")
        _ih_ok = False
        _ih_err = None
        try:
            with st.spinner("Running image hunt…"):
                _ih_dbg = call_n8n_image_hunt(
                    url=_ih_url,
                    business_summary=st.session_state.get("business_summary", {}),
                    page_summaries=st.session_state.get("tier1_page_summaries", []),
                    tier2_page_summaries=st.session_state.get("tier2_page_summaries", []),
                    asset_candidates=st.session_state.get("asset_candidates", []),
                    mode=mode,
                )
            st.session_state["image_hunt_debug"] = _ih_dbg
            _ih_resp = _ih_dbg.get("_n8n_response_json")
            if isinstance(_ih_resp, list) and _ih_resp and isinstance(_ih_resp[0], dict):
                _ih_resp = _ih_resp[0]
            st.session_state["visual_pack"] = _ih_resp.get("visual_pack") if isinstance(_ih_resp, dict) else None
            _ih_ok = bool(st.session_state.get("visual_pack"))
        except Exception as _ih_e:
            _ih_err = str(_ih_e)
        if _ih_ok:
            st.session_state["image_hunt_done"] = True
            st.success("Image hunt complete.")
            
            # Auto-run generate_ad_concepts after image hunt succeeds
            with st.spinner("Generating poster concepts..."):
                _vp = st.session_state.get("visual_pack") or {}
                _image_urls = []
                if isinstance(_vp, dict):
                    _vp_imgs = _vp.get("images", [])
                    if isinstance(_vp_imgs, list):
                        _image_urls = [img.get("url") for img in _vp_imgs if isinstance(img, dict) and img.get("url")]
                
                _concepts_dbg = call_n8n_generate_ad_concepts(
                    business_summary=st.session_state.get("business_summary", {}),
                    page_summaries=st.session_state.get("tier1_page_summaries", []),
                    homepage_markdown=st.session_state.get("homepage_markdown", ""),
                    image_urls=_image_urls,
                    mode=mode,
                )
                st.session_state["concepts_debug"] = _concepts_dbg
                
                _concepts_resp = _concepts_dbg.get("_n8n_response_json")
                if isinstance(_concepts_resp, list) and _concepts_resp and isinstance(_concepts_resp[0], dict):
                    _concepts_resp = _concepts_resp[0]
                
                if isinstance(_concepts_resp, dict) and _concepts_resp.get("poster_concepts"):
                    st.session_state["poster_concepts"] = _concepts_resp.get("poster_concepts")
                    st.success("Poster concepts generated!")
                else:
                    st.warning("Poster concepts workflow returned empty response")
            st.rerun()
        else:
            st.session_state["image_hunt_done"] = False
            st.error(f"Image hunt failed: {_ih_err or 'no visual_pack returned'}")

    # 2nd-pass text analysis
    can_run_check = bool(st.session_state.get("scrape_pack"))
    if st.button("Re-analyse text (2nd pass)", disabled=not can_run_check, use_container_width=True):
        target_url = st.session_state.get("target_url", "")
        _run_check_text_blobs_now(target_url=target_url)
        st.success("2nd pass complete.")

    st.divider()

    if st.button("🔄 Reset & start over", use_container_width=True):
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
        st.session_state["tier2_page_summaries"] = []
        st.session_state["tier2_decision"] = {}
        st.session_state["asset_candidates"] = []
        st.session_state["image_hunt_done"] = False
        st.session_state["image_hunt_debug"] = None
        st.session_state["image_hunt_error"] = None
        st.session_state["visual_pack"] = None
        st.session_state["image_carousel_index"] = 0
        st.session_state["image_carousel_last_advance"] = 0
        st.session_state["concept_visual_packs"] = {}
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
    st.caption("Scan complete — now reviewing your key pages.")
elif status == "analysing_pages":
    st.caption("Reviewing key pages for advertising material...")
elif status == "summarising":
    if st.session_state.get("homepage_summarise_done"):
        st.caption("Creating your campaign concepts...")
    else:
        st.caption("Building your business summary...")
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

if (tiers.get(1) or tiers.get(2)) and status in ("scraped", "summarising", "analysing_pages", "finding_images", "generating_ads", "done"):
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

# --- Key page highlights (snippets from tier 1/2, shown inline with URL cards) ---
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

_page_summaries = st.session_state.get("tier1_page_summaries", [])
if isinstance(_page_summaries, list) and _page_summaries:
    st.caption("Key advertising material we found on your pages:")
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

# --- Tier 2 decision + results ---
_t2_decision = st.session_state.get("tier2_decision", {})
_t2_summaries = st.session_state.get("tier2_page_summaries", [])
if isinstance(_t2_decision, dict) and _t2_decision:
    if _t2_decision.get("should_scrape") and isinstance(_t2_summaries, list) and _t2_summaries:
        st.caption(f"Additional pages reviewed: {_t2_decision.get('reasoning', '')}")
        st.markdown(_highlight_css, unsafe_allow_html=True)
        for ps in _t2_summaries:
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
    else:
        st.caption(f"Deeper pages reviewed — none needed. {_t2_decision.get('reasoning', '')}")

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

# Step 1: Tier 1 summarise (extract snippets from key pages first)
if status == "scraped" and not st.session_state.get("tier1_summarise_done", False):
    st.session_state["scrape_status"] = "analysing_pages"

    tier1_urls = pack.get("tier1_urls", []) or []
    tier2_urls = pack.get("tier2_urls", []) or []
    # No business_summary yet — send empty dict; tier1 prompt doesn't depend on it heavily
    bs = st.session_state.get("business_summary", {}) or {}

    with st.spinner("Reviewing your key pages for advertising material..."):
        t1_debug = call_n8n_tier1_summarise(
            url=target_url,
            tier1_urls=tier1_urls,
            tier2_urls=tier2_urls,
            business_summary=bs,
            mode=st.session_state.get("n8n_mode", "TEST"),
        )
    st.session_state["tier1_summarise_debug"] = t1_debug

    # Hydrate tier1_page_summaries + optional tier2 results from response
    resp_json = t1_debug.get("_n8n_response_json")
    try:
        if isinstance(resp_json, list) and resp_json and isinstance(resp_json[0], dict):
            resp_json = resp_json[0]
        if isinstance(resp_json, dict):
            ps = resp_json.get("page_summaries")
            if isinstance(ps, list):
                st.session_state["tier1_page_summaries"] = ps
            # Tier 2 results (if the decision agent chose to scrape)
            t2ps = resp_json.get("tier2_page_summaries")
            if isinstance(t2ps, list) and t2ps:
                st.session_state["tier2_page_summaries"] = t2ps
            t2d = resp_json.get("tier2_decision")
            if isinstance(t2d, dict):
                st.session_state["tier2_decision"] = t2d
            ac = resp_json.get("asset_candidates", [])
            if isinstance(ac, list):
                st.session_state["asset_candidates"] = ac
    except Exception:
        pass

    st.session_state["tier1_summarise_done"] = True
    st.rerun()

# Step 2: Homepage summarise (now has snippets from tier1/tier2 for richer context)
status = st.session_state.get("scrape_status", "idle")
if status == "analysing_pages" and not st.session_state.get("homepage_summarise_done", False):
    st.session_state["scrape_status"] = "summarising"

    # Gather all page summaries (tier1 + tier2) for the homepage summariser
    all_snippets = list(st.session_state.get("tier1_page_summaries", []) or [])
    all_snippets += list(st.session_state.get("tier2_page_summaries", []) or [])

    with st.spinner("Building a summary of your business..."):
        hp_debug = call_n8n_homepage_summarise(
            url=target_url,
            homepage_markdown=homepage_md,
            page_summaries=all_snippets,
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

#
# CAROUSEL DISPLAY — Always show candidate images with contextual messaging
#

st.subheader("About your business")
bs = st.session_state.get("business_summary", {})
if isinstance(bs, dict) and bs:
    st.caption("From a scan of your website, here is a first-draft summary:")
    st.markdown(f"**Name:** {bs.get('name_guess','')}")
    st.markdown(f"**Category:** {bs.get('category','')}")
    st.markdown(f"**Value prop:** {bs.get('value_prop','')}")
    st.markdown(f"**Target customer:** {bs.get('target_customer','')}")
    st.markdown(f"**Tone:** {bs.get('tone','')}")
else:
    st.info("We're still working on this. It will appear here shortly.")

st.divider()


#
# Step 3: Generate ads (chains after homepage summarise — image hunt now runs per-concept on demand)
#
status = st.session_state.get("scrape_status", "idle")
if (
    status == "summarising"
    and st.session_state.get("homepage_summarise_done", False)
    and not st.session_state.get("ads_autorun_done", False)
):
    st.session_state["scrape_status"] = "generating_ads"

    # ensure inputs exist (derive from V2 if needed)
    if not st.session_state.get("scraped_text") and st.session_state.get("scrape_pack"):
        txt, urls = _derive_inputs_from_scrape_pack(st.session_state["scrape_pack"])
        st.session_state["scraped_text"] = txt
        st.session_state["scraped_images"] = urls

    # Prefer homepage_markdown from scrape-pack V2 payload if available
    homepage_md = st.session_state.get("homepage_markdown") or ""
    sp = st.session_state.get("scrape_pack")
    if not homepage_md and isinstance(sp, dict):
        homepage_md = sp.get("homepage_markdown") or ""
        if homepage_md:
            st.session_state["homepage_markdown"] = homepage_md

    # Combine tier1 + tier2 snippets (these exist if tier1_summarise ran)
    all_page_summaries = []
    t1 = st.session_state.get("tier1_page_summaries") or []
    t2 = st.session_state.get("tier2_page_summaries") or []
    if isinstance(t1, list):
        all_page_summaries.extend([x for x in t1 if isinstance(x, dict)])
    if isinstance(t2, list):
        all_page_summaries.extend([x for x in t2 if isinstance(x, dict)])

    can_autorun = bool(
        st.session_state.get("scraped_text")
        or st.session_state.get("business_summary")
        or all_page_summaries
    )
    if can_autorun:
        with st.spinner("Creating your campaign concepts..."):
            debug_result = call_n8n_generate_ads(
                url=target_url,
                scraped_text=st.session_state.get("scraped_text", ""),
                image_urls=st.session_state.get("scraped_images", []),
                homepage_markdown=homepage_md,
                page_summaries=all_page_summaries,
                business_summary=st.session_state.get("business_summary") or {},
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

# =============================================================================
# ALL CANDIDATE IMAGES — carousel above concepts so users can see the pool first
# =============================================================================

_raw_candidates = st.session_state.get("asset_candidates", [])

if isinstance(_raw_candidates, list) and _raw_candidates:
    st.header("Images from your website")
    st.caption(
        f"All {len(_raw_candidates)} images harvested from your site. "
        "When you click **Generate Poster** on a concept below, our AI reviews every one of these "
        "and selects the best matches for that specific concept."
    )

    # Filter to likely renderable images (skip data URIs, SVG inlines, tiny icons)
    _preview_urls = []
    for _c in _raw_candidates:
        if not isinstance(_c, dict):
            continue
        u = _c.get("url", "")
        if not u or not isinstance(u, str):
            continue
        if u.startswith("data:") or u == "__INLINE_SVG__":
            continue
        if (_c.get("kind") or "").lower() == "svg_inline":
            continue
        _preview_urls.append(u)

    if _preview_urls:
        st.markdown(f"**{len(_preview_urls)} candidate images — auto-scrolling preview:**")

        import time as _time
        if "image_carousel_index" not in st.session_state:
            st.session_state["image_carousel_index"] = 0
        if "image_carousel_last_advance" not in st.session_state:
            st.session_state["image_carousel_last_advance"] = 0.0

        # Auto-advance every 2 seconds
        _now = _time.time()
        if _now - st.session_state["image_carousel_last_advance"] >= 2.0:
            st.session_state["image_carousel_index"] = (
                st.session_state["image_carousel_index"] + 1
            ) % len(_preview_urls)
            st.session_state["image_carousel_last_advance"] = _now
            st.rerun()

        carousel_cols = st.columns(3)
        _start_idx = st.session_state["image_carousel_index"] % len(_preview_urls)
        for col_idx, col in enumerate(carousel_cols):
            _image_idx = (_start_idx + col_idx) % len(_preview_urls)
            with col:
                try:
                    st.image(_preview_urls[_image_idx], use_container_width=True)
                    st.caption(f"Image {_image_idx + 1}/{len(_preview_urls)}")
                except Exception:
                    st.info("Preview unavailable")

        with st.expander("Browse manually"):
            col1, col2 = st.columns(2)
            with col1:
                if st.button("◀ Previous", use_container_width=True):
                    st.session_state["image_carousel_index"] = (
                        st.session_state["image_carousel_index"] - 1
                    ) % len(_preview_urls)
                    st.session_state["image_carousel_last_advance"] = _time.time()
                    st.rerun()
            with col2:
                if st.button("Next ▶", use_container_width=True):
                    st.session_state["image_carousel_index"] = (
                        st.session_state["image_carousel_index"] + 1
                    ) % len(_preview_urls)
                    st.session_state["image_carousel_last_advance"] = _time.time()
                    st.rerun()

st.divider()

# =============================================================================
# CAMPAIGN CONCEPTS — each concept has its own Generate Poster flow
# =============================================================================

st.subheader("Campaign concepts")
concepts = st.session_state.get("poster_concepts", [])

if not concepts:
    st.info("Concepts will appear here once generation is complete.")
else:
    for i, concept in enumerate(concepts):
        with st.container(border=True):
            c_left, c_right = st.columns([3, 2])

            with c_left:
                name = concept.get("concept_name", f"Concept {i + 1}")
                st.markdown(f"### {name}")
                st.markdown(f"**Headline:** {concept.get('headline','')}")
                st.markdown(f"**Supporting copy:** {concept.get('supporting_copy','')}")
                st.markdown(f"**CTA:** {concept.get('cta','')}")
                st.markdown(f"**Image idea:** {concept.get('image_idea','')}")
                st.markdown(f"**Layout notes:** {concept.get('layout_notes','')}")
                tags = concept.get("style_tags") or []
                if isinstance(tags, list) and tags:
                    st.caption("Style tags: " + ", ".join([str(t) for t in tags]))

            with c_right:
                cvp = st.session_state.get("concept_visual_packs", {})
                img_cache = st.session_state.get("poster_images", {}) or {}

                # Show generated poster if we have one
                if i in img_cache:
                    st.image(img_cache[i], use_container_width=True)

                # Show curated images for this concept if image hunt has run
                if i in cvp:
                    vp_i = cvp[i] or {}
                    vp_imgs = vp_i.get("images", []) or []
                    vp_logos = vp_i.get("logos", []) or []
                    vp_brand = vp_i.get("brand", {}) or {}

                    if vp_imgs:
                        st.markdown("**Images selected for this concept:**")
                        thumb_cols = st.columns(min(len(vp_imgs[:6]), 3))
                        for ti, im in enumerate(vp_imgs[:6]):
                            if not isinstance(im, dict):
                                continue
                            img_url = im.get("url", "")
                            if not img_url:
                                continue
                            with thumb_cols[ti % 3]:
                                try:
                                    st.image(img_url, use_container_width=True)
                                    type_label = im.get("type", "")
                                    use_label = im.get("recommended_use", "")
                                    if type_label or use_label:
                                        st.caption(" | ".join(filter(None, [type_label, use_label])))
                                    if im.get("why_relevant"):
                                        st.caption(im["why_relevant"])
                                except Exception:
                                    pass

                    if vp_logos:
                        st.markdown("**Logos:**")
                        logo_c = st.columns(min(len(vp_logos[:3]), 3))
                        for li, logo in enumerate(vp_logos[:3]):
                            if isinstance(logo, dict) and logo.get("url"):
                                with logo_c[li]:
                                    try:
                                        st.image(logo["url"], use_container_width=True)
                                    except Exception:
                                        pass

                    # Brand cues summary
                    colors = vp_brand.get("colors", [])
                    if isinstance(colors, list) and colors:
                        color_text = ", ".join(
                            f"{c.get('hex', '?')} ({c.get('role', '?')})"
                            for c in colors if isinstance(c, dict)
                        )
                        if color_text:
                            st.caption(f"Brand colours: {color_text}")

                # --- Generate Poster button ---
                # Triggers: (1) concept-specific image hunt across ALL candidates,
                #           then (2) n8n two-stage poster generation (LLM selects images → LLM builds DALL-E prompt → DALL-E generates image).
                if i not in img_cache:
                    if st.button("Generate Poster", key=f"gen_poster_{i}", use_container_width=True, type="primary", disabled=st.session_state.get("generate_image_pending", False)):
                        bs = st.session_state.get("business_summary", {}) or {}

                        # Step 1: Run image hunt for this specific concept
                        all_candidates = st.session_state.get("asset_candidates", [])
                        concept_vp_result = None
                        if all_candidates:
                            try:
                                with st.spinner("Searching for the best images for this concept..."):
                                    hunt_dbg = call_n8n_image_hunt(
                                        url=st.session_state.get("target_url", ""),
                                        business_summary=bs,
                                        page_summaries=st.session_state.get("tier1_page_summaries", []),
                                        tier2_page_summaries=st.session_state.get("tier2_page_summaries", []),
                                        asset_candidates=all_candidates,
                                        concept=concept,
                                        mode=st.session_state.get("n8n_mode", "TEST"),
                                    )
                                hunt_resp = hunt_dbg.get("_n8n_response_json")
                                if isinstance(hunt_resp, list) and hunt_resp and isinstance(hunt_resp[0], dict):
                                    hunt_resp = hunt_resp[0]
                                concept_vp = hunt_resp.get("visual_pack") if isinstance(hunt_resp, dict) else None
                                if concept_vp:
                                    cvp_store = st.session_state.get("concept_visual_packs", {})
                                    cvp_store[i] = concept_vp
                                    st.session_state["concept_visual_packs"] = cvp_store
                                    concept_vp_result = concept_vp
                            except Exception as hunt_err:
                                st.warning(f"Image search encountered an issue: {hunt_err}")

                        # Step 2: Collect image URLs and build guidelines for n8n poster workflow
                        if concept_vp_result is None:
                            concept_vp_result = st.session_state.get("concept_visual_packs", {}).get(i, {})
                        vp_images = concept_vp_result.get("images") or []
                        vp_logos = concept_vp_result.get("logos") or []
                        vp_brand = concept_vp_result.get("brand") or {}

                        # Gather all curated image URLs for n8n's image-selection LLM
                        poster_image_urls = [
                            im.get("url") for im in vp_images
                            if isinstance(im, dict) and im.get("url")
                        ]
                        for lg in vp_logos:
                            if isinstance(lg, dict) and lg.get("url"):
                                poster_image_urls.append(lg["url"])

                        # Build guidelines dict from business summary + brand cues
                        guidelines = {
                            "business_name": bs.get("name_guess", ""),
                            "category": bs.get("category", ""),
                            "tone": bs.get("tone", ""),
                            "value_proposition": bs.get("value_proposition", ""),
                            "brand_colors": vp_brand.get("colors", []),
                            "brand_fonts": vp_brand.get("fonts", []),
                            "brand_motifs": vp_brand.get("motifs", []),
                            "logo_url": vp_logos[0].get("url", "") if vp_logos else "",
                            "ooh_requirements": {
                                "legible_at_100ft": True,
                                "negative_space_60pct": True,
                                "single_dominant_focal": True,
                                "logo_placement": "bottom-right at ~8% of poster area",
                            },
                        }

                        # Do NOT call n8n inline in the loop. Store intent; process once after loop.
                        st.session_state["generate_image_pending"] = True
                        st.session_state["generate_image_error"] = None
                        st.session_state["generate_image_request"] = {
                            "concept_index": i,
                            "concept": concept,
                            "guidelines": guidelines,
                            "image_urls": poster_image_urls,
                        }
                        st.rerun()

    # ---- Process any pending image generation request (single-shot) ----
    req = st.session_state.get("generate_image_request")
    if st.session_state.get("generate_image_pending") and isinstance(req, dict):
        i = req.get("concept_index")
        concept = req.get("concept", {})
        guidelines = req.get("guidelines", {})
        poster_image_urls = req.get("image_urls", [])
        try:
            with st.spinner("Generating your poster (selecting images, building prompt, rendering)..."):
                img_res = call_n8n_generate_poster(
                    poster_concept=concept,
                    guidelines=guidelines,
                    image_urls=poster_image_urls,
                    mode=st.session_state.get("n8n_mode", "TEST"),
                )
                if not img_res.get("ok"):
                    raise RuntimeError(
                        img_res.get("response_text_snippet", "n8n poster call failed")
                    )
                resp = img_res.get("response_json") or {}
                b64 = (resp or {}).get("image_b64", "")
                if not b64:
                    raise RuntimeError("Missing image_b64 in n8n response")
                img_bytes = base64.b64decode(b64)

            # Success: store bytes and clear pending
            st.session_state["poster_images"][i] = img_bytes
            st.session_state["generate_image_pending"] = False
            st.session_state["generate_image_request"] = None
            st.session_state["generate_image_error"] = None
            st.rerun()
        except Exception as e:
            # Failure: clear pending but keep error visible (do not require double clicks)
            st.session_state["generate_image_pending"] = False
            st.session_state["generate_image_error"] = str(e)
            st.session_state["generate_image_request"] = None
            st.warning(f"Poster generation failed: {e}")

st.divider()

# =============================================================================
# DEVELOPER DIAGNOSTICS
# =============================================================================

with st.expander("Developer diagnostics (scrape + requests)", expanded=False):
    st.subheader("Scrape-pack output (debug)")
    sp = st.session_state.get("scrape_pack")
    if sp:
        st.json(sp)
    else:
        st.info("No scrape-pack payload yet (check debug below).")

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

    ads_dbg = st.session_state.get("ads_debug")
    if ads_dbg:
        st.subheader("Debug: generate-ads request/response")
        st.code(ads_dbg.get("_debug_target_url", ""), language="text")
        if ads_dbg.get("_error"):
            st.error(ads_dbg.get("_error"))
        st.json(ads_dbg.get("_debug_payload_sent", {}))
        st.json(ads_dbg.get("_n8n_response_json", {}))

    img_dbg = st.session_state.get("image_hunt_debug")
    if img_dbg:
        st.subheader("Debug: last image-hunt request/response")
        st.code(img_dbg.get("_debug_target_url", ""), language="text")
        if img_dbg.get("_error"):
            st.error(img_dbg.get("_error"))
        payload = img_dbg.get("_debug_payload_sent", {})
        display_payload = dict(payload)
        if "asset_candidates" in display_payload and isinstance(display_payload["asset_candidates"], list):
            display_payload["asset_candidates"] = f"[{len(display_payload['asset_candidates'])} items]"
        if "page_summaries" in display_payload and isinstance(display_payload["page_summaries"], list):
            display_payload["page_summaries"] = f"[{len(display_payload['page_summaries'])} items]"
        st.json(display_payload)
        st.json(img_dbg.get("_n8n_response_json", {}))

    st.subheader("Scraped pages")
    visited = st.session_state.get("visited_urls", [])
    if visited:
        for u in visited:
            st.write(f"- {u}")
    else:
        st.write("No pages scraped yet.")

    scraped_text = st.session_state.get("scraped_text", "")
    if scraped_text:
        st.subheader("Scraped text")
        st.text_area("Extracted text", scraped_text, height=240)
