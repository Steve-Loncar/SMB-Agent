# SMB Ad Agent — Current System Architecture (Assistant-Optimized)

> Purpose: give contributors and coding assistants a high-signal map of the **actual running system** so they can work safely without re-reading the whole repository.

---

## 1) What this system does

The SMB Ad Agent takes a business URL and produces:

1. A structured business summary
2. Evidence-backed campaign concepts
3. Optional curated visual packs from site imagery
4. Concept-specific generated poster images

Primary runtime architecture:

`Streamlit UI (Python) -> backend/n8n_client.py -> n8n webhooks -> LLM/image APIs -> Streamlit session state`

---

## 2) Runtime entrypoints and ownership

## Streamlit pages

- `app.py`
  - Minimal landing shell + top nav.
  - Calls `initstate()` and routes users to Home/Results.

- `pages/01_home.py`
  - Collects URL and mode (`TEST` / `LIVE`).
  - Initializes pipeline by setting `scrape_status = "queued"`.
  - Clears downstream state to avoid stale cross-run artifacts.
  - Navigates to `pages/02_results.py`.

- `pages/02_results.py` (**main orchestrator**)
  - Runs the auto pipeline from queued URL.
  - Hosts manual controls for re-running each stage.
  - Renders summaries, page evidence, candidate image carousel, concept cards, and generated posters.
  - Owns most practical state transitions and user-facing status messaging.

## Backend modules

- `backend/state.py`
  - Defines baseline session keys and defaults (core app state).

- `backend/n8n_client.py` (**integration contract layer**)
  - Resolves endpoint URLs by mode/env.
  - Loads prompt templates from `prompts/`.
  - Sends typed payloads to n8n webhooks.
  - Returns debug-rich envelopes (`_debug_*`, `_n8n_response_json`, `_error`).

- `backend/brand_extractor.py`
  - Extracts CSS brand cues from the homepage (colors/fonts/theme/og:image).
  - Merges cues into `business_summary.brand_visual` to enrich poster guidance.

- `backend/scraper.py`
  - Legacy local scraper (not the main path now).

- `backend/image_gen.py`
  - Deprecated by design; generation must go via n8n.

---

## 3) End-to-end flow (current behavior)

## Stage A — URL capture + queue

- Trigger: user clicks **Apply** in `01_home.py`.
- Key effects:
  - Saves `target_url`, mode, scrape knobs.
  - Resets prior artifacts (`poster_concepts`, `visual_pack`, `poster_images`, etc.).
  - Sets `scrape_status = "queued"`.

## Stage B — Scrape pack

- Trigger: `02_results.py` sees `scrape_status == "queued"`.
- Client call: `call_n8n_scrape_pack()`.
- Webhook path: `/webhook(-test)/scrape-pack`.
- Expected normalized payload shape used downstream:

```json
{
  "homepage_url": "...",
  "homepage_markdown": "...",
  "tier1_urls": ["..."],
  "tier2_urls": ["..."]
}
```

- App hydrates compatibility fields:
  - `scraped_text`
  - `scraped_images` (often empty in new shape)
  - `visited_urls`
- Status transitions to `scraped`.

## Stage C — Tier 1 summarise (+ optional tier2)

- Trigger: `scrape_status == "scraped"` and not done.
- Client call: `call_n8n_tier1_summarise()`.
- Webhook path: `/webhook(-test)/SMB-tier1-summariser`.
- Inputs include:
  - `tier1_urls`, `tier2_urls`, `business_summary` (can be empty initially)
  - tier1 + tier2 decision prompts.
- Stores:
  - `tier1_page_summaries`
  - `tier2_page_summaries` (if workflow decides to crawl)
  - `tier2_decision`
  - `asset_candidates`
- Status transitions to `analysing_pages` then rerun.

## Stage D — Homepage summarise (business profile)

- Trigger: `scrape_status == "analysing_pages"` and not done.
- Client call: `call_n8n_homepage_summarise()`.
- Webhook path: `/webhook(-test)/SMB-homepage-summarise`.
- Inputs:
  - homepage markdown
  - tier1/tier2 snippets
- Stores:
  - `business_summary`
- Merge step:
  - `css_brand_cues` from `backend/brand_extractor.py` are merged into `business_summary.brand_visual`.
- Status transitions to `summarising` then rerun.

## Stage E — Concept generation (auto-run)

- Trigger: `scrape_status == "summarising"` + summary done + not autorun done.
- Client call: `call_n8n_generate_ad_concepts()`.
- Webhook path: `/webhook(-test)/SMB-generate-ad-concepts`.
- Stores:
  - `poster_concepts`
  - `poster_images` reset
  - `ads_autorun_done = True`
  - `scrape_status = "done"`

## Stage F — Image hunt (optional/manual)

- Trigger: manual sidebar button **④ Global Image Hunt**.
- Client call: `call_n8n_image_hunt()`.
- Webhook path: `/webhook(-test)/SMB-image-hunt`.
- Pre-filtering: `_filter_asset_candidates()` in Python removes junk + dedupes + caps.
- Stores:
  - `visual_pack`
  - `image_hunt_done`
- Then auto-runs concept generation again using visual pack image URLs.

## Stage G — Poster generation per concept

- Trigger: **Generate Poster** button on each concept card.
- Client call: `call_n8n_generate_poster()`.
- Endpoint currently resolves to same path as generate image:
  - `/webhook(-test)/generate-image`
- n8n workflow (`smb_image_gen.json`) performs internal stages:
  1. Select best images for this concept
  2. Build poster prompt
  3. Call image model and return base64 image
- App decodes `image_b64` and caches bytes in `poster_images[concept_index]`.

---

## 4) n8n integration contracts (practical map)

## Webhook resolution

`backend/n8n_client.py::resolve_n8n_webhook()` is the single source of truth.

- Mode-aware: `TEST` / `LIVE`
- Supports explicit env URL overrides per endpoint
- Defaults to `N8N_BASE_URL` or hardcoded n8n cloud base
- Adds webhook secret header if `WEBHOOK_SECRET`/`N8N_WEBHOOK_SECRET` is set

## Endpoints used by UI

- `scrape_pack` -> `/scrape-pack`
- `tier1_summarise` -> `/SMB-tier1-summariser`
- `homepage_summarise` -> `/SMB-homepage-summarise`
- `generate_ad_concepts` -> `/SMB-generate-ad-concepts`
- `image_hunt` -> `/SMB-image-hunt`
- `generate_poster` -> `/generate-image`
- `check_text_blobs` -> `/check-text-blobs` (manual diagnostics / fallback)

## Workflow files in active SMB path

Primary workflow directory:

`workflows/fpgconsulting_cloud_steve_l/my_project/`

Core SMB workflows relevant to runtime:

- `SMB-scrape-pack.json`
- `SMB_tier1_summariser.json`
- `SMB_homepage_summariser.workflow.ts` (TS source currently present for homepage summariser)
- `SMB_generate_ad_concepts.json`
- `SMB_Image_hunt.json`
- `smb_image_gen.json`
- `SMB_check_text_blobs_generate_business_summary.json` (manual re-analysis path)

---

## 5) Prompt architecture (source of model behavior)

Prompt files live in `prompts/` and are loaded in Python before webhook calls.

Key prompt groups:

- Concepts:
  - `smb_generate_ad_concepts_system.txt`
  - `smb_generate_ad_concepts_user.txt`

- Homepage summary:
  - `smb_homepage_summarise_system.txt`
  - `smb_homepage_summarise_user.txt`

- Tier analysis:
  - `smb_tier1_summarise_system.txt`
  - `smb_tier1_summarise_user.txt`
  - `smb_tier2_decision_system.txt`
  - `smb_tier2_decision_user.txt`

- Image hunt:
  - `smb_image_hunt_system.txt`
  - `smb_image_hunt_user.txt`

- Poster generation:
  - `smb_image_selection_system.txt`
  - `smb_image_selection_user.txt`
  - `smb_poster_gen_system.txt`
  - `smb_poster_gen_user.txt`

Legacy but still present:

- `smb_generate_ads_system.txt`
- `smb_generate_ads_user.txt`

Note: current auto pipeline prefers `generate_ad_concepts` path; `generate_ads` helpers remain in client for compatibility.

---

## 6) Session state model (keys that matter most)

## Control / mode

- `target_url`
- `n8n_mode` (`TEST`/`LIVE`)
- `scrape_status` (`idle`, `queued`, `scraped`, `analysing_pages`, `summarising`, `generating_ads`, `done`, `error`)

## Core data artifacts

- `scrape_pack`
- `homepage_markdown`
- `tier1_page_summaries`
- `tier2_page_summaries`
- `tier2_decision`
- `business_summary`
- `asset_candidates`
- `visual_pack`
- `poster_concepts`
- `poster_images` (bytes cache by index)

## Flow guards / booleans

- `tier1_summarise_done`
- `homepage_summarise_done`
- `ads_autorun_done`
- `check_text_blobs_autorun_done`
- `image_hunt_done`

## Diagnostics

- `scrape_pack_debug`
- `tier1_summarise_debug`
- `homepage_summarise_debug`
- `ads_debug`
- `image_hunt_debug`
- `check_text_blobs_debug`
- `poster_gen_debug`

## UX helpers

- `image_carousel_index`
- `image_carousel_last_advance`
- `concept_visual_packs`

---

## 7) Response envelope pattern (important for robust code)

Most `backend/n8n_client.py` functions return a common shape:

- `_debug_target_url`
- `_debug_payload_sent`
- `_debug_http_status`
- `_debug_resp_text_snippet`
- `_n8n_response_json` (if parseable)
- `_error` (if non-200 or fatal issue)

Consumer logic in `02_results.py` often handles both:

- direct dict response
- `respondWith: allIncomingItems` list-wrapped response (`[ { ... } ]`)

When adding integrations, preserve this envelope to avoid silent UI regressions.

---

## 8) Active UI surfaces in Results page

User-visible blocks:

1. Narrative progress header
2. Website scan pages (key vs supporting)
3. Tier 1 / Tier 2 snippet cards
4. Business summary + brand visual evidence
5. Candidate image carousel
6. Campaign concept cards
7. Per-concept poster generation controls
8. Developer diagnostics expander

Manual controls in sidebar:

- Re-run page analysis
- Re-run business summary
- Generate concepts
- Global image hunt
- Re-analyse text (2nd pass)
- Reset & start over

---

## 9) Known architectural nuances and gotchas

1. `smb_image_gen` has historically had JSON/TS sync drift; runtime currently depends on the JSON webhook contract consumed by Python.
2. Homepage summariser currently appears as `.workflow.ts` in repo; ensure exports stay in sync if editing in n8n UI.
3. `scraper.py` is not the primary path; avoid introducing mixed local-scrape + n8n-scrape logic unless deliberate.
4. Auto-rerun logic in Streamlit depends on guard flags; if a stage seems skipped/repeated, inspect `*_done` flags first.
5. Debug blocks are intentionally verbose and useful for diagnosing schema drifts from n8n.

---

## 10) Assistant playbook (how to make safe changes fast)

If changing this system, follow this order:

1. Identify stage owner (`02_results.py` orchestration vs `n8n_client.py` contract vs workflow JSON).
2. Update prompt/template and payload contract together.
3. Preserve response envelope fields and list-wrapper parsing.
4. Confirm session state reset paths in both:
   - `01_home.py` on Apply
   - `02_results.py` Reset button
5. Re-check endpoint path in `resolve_n8n_webhook()`.
6. Validate that manual controls still work after auto-flow changes.

---

## 11) Minimal file map for fast onboarding

Read these first (in order):

1. `pages/02_results.py` — orchestration truth
2. `backend/n8n_client.py` — webhook contract truth
3. `backend/state.py` — state keys/defaults
4. `pages/01_home.py` — pipeline entry/reset
5. Core workflows under `workflows/fpgconsulting_cloud_steve_l/my_project/`

Then read prompts for behavior tuning.

---

## 12) Last updated scope

This document reflects current repository runtime wiring as of the latest synced `main` branch, with emphasis on:

- Streamlit auto + manual pipeline behavior
- n8n webhook contracts and payload envelopes
- Prompt and session-state dependencies
- Poster generation and image-hunt integration details
