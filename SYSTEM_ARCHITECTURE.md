# 🎯 SMB Ad Agent: System Architecture & Optimization Guide

> **Purpose:** Generate professional UK OOH (Out-of-Home) advertising campaigns for SMBs from their websites using a multi-stage AI pipeline.

---

## 🏗️ Architecture Overview

### Stack
- **Frontend:** Streamlit (Python) - `app.py`, `pages/01_home.py`, `pages/02_results.py`
- **Backend:** n8n Cloud workflows (webhook-triggered)
- **AI Models:** OpenAI GPT-4o (analysis), DALL-E 3 (image generation)
- **Integration:** Python → HTTP → n8n → OpenAI APIs → Python

### Data Flow Pattern
```
User URL → Scrape → Tier 1 Analysis → Homepage Summary → 
Image Hunt → Generate Concepts → Generate Posters
```

---

## 📂 Project Structure

### Python Files (Streamlit)

#### `app.py`
- Entry point, basic landing page
- Sets up page config and navigation

#### `pages/01_home.py`
- **Purpose:** URL input, scrape configuration
- **Key Actions:**
  - User enters website URL
  - Sets scrape depth (homepage_only | homepage_plus)
  - Triggers scrape queue
  - **Session State:** `target_url`, `scrape_depth`, `scrape_max_pages`, `n8n_mode`

#### `pages/02_results.py` ⭐ **MAIN ORCHESTRATOR**
- **Purpose:** Workflow orchestration, results display, controls
- **Role:** Triggers all n8n workflows in sequence, manages state, displays outputs
- **Key Features:**
  - Auto-triggers workflows when data is ready
  - Manual re-run buttons for each stage
  - Poster concept carousel with image generation
  - Session state management for entire pipeline

### Backend Files

#### `backend/n8n_client.py` ⭐ **API CLIENT**
- **Purpose:** All n8n webhook communication
- **Key Functions:**
  - `call_n8n_scrape_pack()` - Scrapes website
  - `call_n8n_tier1_summarise()` - Page-level analysis
  - `call_n8n_homepage_summarise()` - Business summary
  - `call_n8n_image_hunt()` - Curate on-brand images
  - `call_n8n_generate_ad_concepts()` - Generate campaign concepts
  - `call_n8n_generate_poster()` - Multi-stage poster generation
  - `resolve_n8n_webhook()` - URL resolution (TEST/LIVE modes)

#### `backend/state.py`
- **Purpose:** Session state initialization
- **Key States:** URL, scrape data, summaries, concepts, images, flags

#### `backend/scraper.py`
- (Legacy/unused) - scraping now handled by n8n workflow

#### `backend/image_gen.py`
- (Deprecated) - image generation now in n8n workflows

---

## 🔄 Workflow Pipeline (End-to-End)

### Stage 0: Scrape Website
**Workflow:** `SMB-scrape-pack.json`  
**Trigger:** Auto (on page load if URL set) or Manual button  
**Endpoint:** `/webhook/scrape-pack`  
**Prompts:** None (pure scraping)

**Input:**
- `url`: Target website URL
- `depth`: `homepage_only` | `homepage_plus`
- `max_pages`: Integer (default 3)

**Output (`scrape_pack`):**
```json
{
  "homepage_url": "https://...",
  "homepage_markdown": "# Homepage content...",
  "homepage_images": ["url1", "url2"],
  "additional_pages": [
    {
      "url": "https://.../about",
      "title": "About Us",
      "markdown": "...",
      "images": ["..."]
    }
  ]
}
```

**Purpose:** Extract homepage + key internal pages as markdown, collect all images.

---

### Stage 1: Tier 1 Page Analysis
**Workflow:** `SMB_tier1_summariser.json`  
**Trigger:** Auto after scrape or Manual button "① Re-run Page Analysis"  
**Endpoint:** `/webhook/SMB-tier1-summariser`

**Prompts:**
- `prompts/smb_tier1_summarise_system.txt`
- `prompts/smb_tier1_summarise_user.txt`

**Input:**
- `url`: Website URL
- `scrape_pack`: Full scrape output
- `business_summary`: (Initial summary if available)

**Processing:**
1. Loop through all pages (homepage + additional)
2. For each page: OpenAI extracts key snippets (services, value props, differentiators, team, process)
3. Collects "asset candidates" (strong image/headline hooks)

**Output:**
```json
{
  "page_summaries": [
    {
      "page_url": "https://.../about",
      "page_title": "About Us",
      "snippets": ["snippet1", "snippet2"],
      "category": "about|services|process|team|..."
    }
  ],
  "asset_candidates": [
    {
      "text": "Award-winning craft",
      "image_url": "https://.../photo.jpg",
      "context": "Homepage hero",
      "why_relevant": "Shows credibility"
    }
  ]
}
```

**Purpose:** Extract structured insights from each page for downstream analysis.

---

### Stage 2: Homepage / Business Summary
**Workflow:** `SMB_check_text_blobs_generate_business_summary.json`  
**Trigger:** Auto after Tier 1 or Manual button "② Re-run Business Summary"  
**Endpoint:** `/webhook/SMB-homepage-summarise`

**Prompts:**
- `prompts/smb_homepage_summarise_system.txt`
- `prompts/smb_homepage_summarise_user.txt`

**Input:**
- `url`: Website URL
- `homepage_markdown`: From scrape_pack
- `page_summaries`: From Tier 1 (all pages combined)

**Processing:**
1. Analyzes homepage content + all page summaries
2. Generates a consolidated business profile

**Output (`business_summary`):**
```json
{
  "name_guess": "Acme Plumbing",
  "category": "Home Services - Plumbing",
  "vertical": "Trades",
  "tone": "Professional, trusted, local",
  "value_proposition": "Emergency response, 20+ years, fixed-price quotes",
  "differentiators": ["24/7 availability", "No call-out fees"],
  "target_audience": "Homeowners, landlords",
  "evidence_strength": "high|medium|low",
  "confidence": 0.85
}
```

**Purpose:** Build a single authoritative business profile for campaign generation.

---

### Stage 3: Generate Campaign Concepts
**Workflow:** `SMB_generate_ad_concepts.json`  
**Trigger:** Auto after Business Summary or Manual button "③ Generate Concepts"  
**Endpoint:** `/webhook/SMB-generate-ad-concepts`

**Prompts:**
- `prompts/smb_generate_ad_concepts_system.txt`
- `prompts/smb_generate_ad_concepts_user.txt`

**Input:**
- `url`: Website URL
- `business_summary`: From Stage 2
- `page_summaries`: Tier 1 + Tier 2 combined

**Processing:**
1. OpenAI generates 3 distinct OOH campaign concepts
2. Each concept has headline, message angle, evidence, tone

**Output (`poster_concepts`):**
```json
{
  "concepts": [
    {
      "concept_name": "The Trust Play",
      "headline": "20 Years. Zero Surprises.",
      "message_angle": "Reliability & transparency",
      "supporting_copy": "Fixed-price quotes. No hidden fees.",
      "cta": "Call 0800...",
      "evidence": ["20+ years in business", "5-star reviews"],
      "tone": "Reassuring, professional",
      "target_emotion": "Confidence"
    },
    { ... },
    { ... }
  ]
}
```

**Purpose:** Create campaign-ready messaging concepts grounded in scraped evidence.

---

### Stage 4: Global Image Hunt
**Workflow:** `SMB_Image_hunt.json`  
**Trigger:** Auto after concepts generated or Manual button "④ Global Image Hunt"  
**Endpoint:** `/webhook/SMB-image-hunt`

**Prompts:**
- `prompts/smb_image_hunt_system.txt`
- `prompts/smb_image_hunt_user.txt`

**Input:**
- `url`: Website URL
- `business_summary`: From Stage 2
- `page_summaries`: All page summaries
- `asset_candidates`: From Tier 1 (image URLs + context)

**Processing:**
1. OpenAI curates best images from all scraped pages
2. Extracts brand colors, fonts, motifs
3. Selects hero images, product shots, textures, logos

**Output (`visual_pack`):**
```json
{
  "images": [
    {
      "url": "https://.../hero.jpg",
      "category": "hero|product|process|texture",
      "why_relevant": "Shows craftsman at work",
      "ooh_suitability": "High - clear focal point",
      "suggested_use": "Background for Trust Play concept"
    }
  ],
  "logos": [
    {
      "url": "https://.../logo.svg",
      "format": "svg|png",
      "background": "transparent|white"
    }
  ],
  "brand": {
    "colors": [
      {"hex": "#1E3A8A", "role": "primary"},
      {"hex": "#FFFFFF", "role": "background"}
    ],
    "fonts": [
      {"name": "Roboto", "weight": "bold", "usage": "headlines"}
    ],
    "motifs": ["rounded corners", "clean minimalism"]
  }
}
```

**Purpose:** Build a brand-consistent visual asset library for poster generation.

---

### Stage 5: Generate Poster (Per Concept)
**Workflow:** `smb_image_gen.json` ⭐ **COMPLEX MULTI-STAGE**  
**Trigger:** Manual button "Generate Poster" on each concept card  
**Endpoint:** `/webhook/generate-image`

**Sub-Stage 5A: Image Selection**
**Prompts:**
- `prompts/smb_image_selection_system.txt`
- `prompts/smb_image_selection_user.txt`

**Input:**
- `poster_concept`: Single concept from Stage 3
- `guidelines`: Business summary + brand cues from visual_pack
- `image_urls`: All curated images from visual_pack

**Processing:**
1. Concept-specific image hunt (selects 5-6 best images for THIS concept)
2. Ensures OOH suitability (negative space, focal point, contrast)

**Output:**
```json
{
  "selected_images": ["url1", "url2", "url3", "url4", "url5"],
  "selection_notes": {
    "concept_name": "The Trust Play",
    "top_reasons": ["Hero shot shows craftsman", "Logo has transparency"],
    "coverage": {
      "includes_background_candidate": true,
      "includes_focal_candidate": true
    }
  }
}
```

**Sub-Stage 5B: Poster Prompt Generation**
**Prompts:**
- `prompts/smb_poster_gen_system.txt`
- `prompts/smb_poster_gen_user.txt`

**Input:**
- `poster_concept`: Same concept
- `selected_images`: From 5A
- `guidelines`: Same guidelines

**Processing:**
1. OpenAI builds a detailed DALL-E prompt
2. Specifies layout, typography, colors, text placement
3. Includes anti-AI-sheen instructions (realistic, professional)

**Output:**
```json
{
  "poster_name": "Trust Play - 20 Years",
  "poster_prompt": "Flat graphic design poster layout (NOT a photographed billboard). 6-sheet portrait format (2:3 aspect). Background: Professional plumber in branded uniform inspecting pipe...",
  "layout_spec": {
    "format": "6-sheet",
    "orientation": "portrait",
    "aspect_ratio": "2:3",
    "type": "classic"
  },
  "asset_plan": {
    "hero_image_url": "https://.../craftsman.jpg",
    "logo_url": "https://.../logo.svg"
  },
  "render_notes": {
    "text_to_render_verbatim": {
      "headline": "20 Years. Zero Surprises.",
      "supporting_copy": "Fixed-price quotes. No call-out fees.",
      "cta": "Call 0800 123 4567"
    },
    "negative_instructions": ["No extra text", "No AI sheen", "No gibberish"]
  }
}
```

**Sub-Stage 5C: DALL-E Image Generation**
**API:** OpenAI DALL-E 3  
**Input:** `poster_prompt` from 5B

**Output:**
- Base64-encoded PNG image
- Stored in `poster_images[concept_index]`

**Purpose:** Generate print-ready poster mockups for each campaign concept.

---

## 🧠 Session State Management

### Critical State Variables

| Variable | Type | Set By | Used By | Purpose |
|----------|------|--------|---------|---------|
| `target_url` | str | Home page | All workflows | Website being analyzed |
| `scrape_pack` | dict | Stage 0 | All stages | Raw scraped data |
| `tier1_page_summaries` | list | Stage 1 | Stages 2,3,4 | Page-level insights |
| `asset_candidates` | list | Stage 1 | Stage 4 | Image/text hooks |
| `business_summary` | dict | Stage 2 | Stages 3,4,5 | Business profile |
| `poster_concepts` | list | Stage 3 | Stage 5 | Campaign concepts |
| `visual_pack` | dict | Stage 4 | Stage 5 | Brand assets |
| `concept_visual_packs` | dict | Stage 5 | Poster display | Per-concept images |
| `poster_images` | dict | Stage 5 | Display | Generated posters |

### Workflow Flags (Auto-trigger Prevention)

| Flag | Prevents | Reset By |
|------|----------|----------|
| `tier1_summarise_done` | Re-running Tier 1 | New URL or manual reset |
| `homepage_summarise_done` | Re-running homepage analysis | New URL or manual reset |
| `ads_autorun_done` | Re-running concept generation | New URL or manual reset |
| `image_hunt_done` | Re-running image hunt | New URL or manual reset |

---

## 🎨 Prompt Architecture

### Naming Convention
`smb_[stage]_[role]_[type].txt`

**Examples:**
- `smb_tier1_summarise_system.txt` - System prompt for Tier 1
- `smb_homepage_summarise_user.txt` - User prompt for homepage summary

### Prompt Pairs (All Stages)

| Stage | System Prompt | User Prompt | n8n Workflow |
|-------|---------------|-------------|--------------|
| Tier 1 Page Analysis | `smb_tier1_summarise_system.txt` | `smb_tier1_summarise_user.txt` | `SMB_tier1_summariser.json` |
| Homepage Summary | `smb_homepage_summarise_system.txt` | `smb_homepage_summarise_user.txt` | `SMB_check_text_blobs_generate_business_summary.json` |
| Generate Concepts | `smb_generate_ad_concepts_system.txt` | `smb_generate_ad_concepts_user.txt` | `SMB_generate_ad_concepts.json` |
| Image Hunt | `smb_image_hunt_system.txt` | `smb_image_hunt_user.txt` | `SMB_Image_hunt.json` |
| Image Selection | `smb_image_selection_system.txt` | `smb_image_selection_user.txt` | `smb_image_gen.json` (sub-stage A) |
| Poster Prompt Gen | `smb_poster_gen_system.txt` | `smb_poster_gen_user.txt` | `smb_image_gen.json` (sub-stage B) |

### Deprecated Prompts (Not in Active Use)
- `smb_generate_ads_system.txt` - Replaced by `smb_generate_ad_concepts_*`
- `smb_generate_ads_user.txt` - Replaced by `smb_generate_ad_concepts_*`
- `smb_tier2_decision_system.txt` - Not currently used
- `smb_tier2_decision_user.txt` - Not currently used

---

## 🔌 N8N Workflow Details

### Active Workflows

#### 1. `SMB-scrape-pack.json`
- **Nodes:** Webhook → Jina.ai Scraper → Response
- **No AI:** Pure HTTP scraping
- **Timeout:** 60s
- **Output Format:** JSON with markdown content + images

#### 2. `SMB_tier1_summariser.json`
- **Nodes:** Webhook → Loop Pages → OpenAI (GPT-4o-mini) → Aggregate → Response
- **AI Model:** gpt-4o-mini (fast, cheap for extraction tasks)
- **Batching:** Processes pages in parallel
- **Output Format:** JSON with page_summaries + asset_candidates

#### 3. `SMB_check_text_blobs_generate_business_summary.json`
- **Nodes:** Webhook → OpenAI (GPT-4o) → Response
- **AI Model:** gpt-4o (needs reasoning for synthesis)
- **Timeout:** 60s
- **Output Format:** JSON with business_summary object

#### 4. `SMB_generate_ad_concepts.json`
- **Nodes:** Webhook → OpenAI (GPT-4o) → Parse JSON → Response
- **AI Model:** gpt-4o (creative + structured output)
- **Response Format:** JSON mode enforced
- **Timeout:** 180s (can be slow for creative tasks)
- **Output Format:** JSON with concepts array

#### 5. `SMB_Image_hunt.json`
- **Nodes:** Webhook → OpenAI (GPT-4o) → Response
- **AI Model:** gpt-4o (visual curation + brand extraction)
- **Timeout:** 120s
- **Output Format:** JSON with visual_pack (images + logos + brand)

#### 6. `smb_image_gen.json` ⭐ **MOST COMPLEX**
- **Nodes:** 
  - Webhook → Normalize Inputs
  - → OpenAI Chat (Image Selection) → Extract Selected
  - → OpenAI Chat (Poster Prompt Gen) → Extract Prompt
  - → DALL-E 3 → Response
- **AI Models:** 
  - gpt-4o (2x for selection + prompt generation)
  - dall-e-3 (final image render)
- **Timeout:** Total ~300s
- **Output Format:** Base64-encoded PNG + metadata

### Workflow Communication Pattern

**Python → n8n:**
```python
response = requests.post(
    url=webhook_url,
    json=payload,
    headers={"Content-Type": "application/json"},
    timeout=(10, 180)  # connect, read
)
```

**n8n → Python:**
```json
{
  "ok": true,
  "response_json": { ... },  // Parsed response
  "_n8n_response_json": { ... },  // Debug envelope
  "_debug_http_status": 200
}
```

---

## 🎯 Optimization Targets

### Performance Bottlenecks (Current)

1. **Stage 3 (Generate Concepts):** 
   - Timeout: 180s
   - Often slow due to creativity demands
   - **Prompt Impact:** High - better structured prompts = faster responses

2. **Stage 5 (Poster Generation):**
   - Total: ~300s (60s + 60s + 180s)
   - DALL-E is slowest (180s)
   - **Prompt Impact:** Medium - better poster prompts = fewer retries

3. **Stage 1 (Tier 1 Analysis):**
   - Batched but can be slow with many pages
   - **Prompt Impact:** High - concise prompts = faster extraction

### Quality Issues (Current)

1. **Concept Relevance:**
   - Sometimes generic, not evidence-led
   - **Prompt Fix:** Strengthen evidence requirement, add constraints

2. **Poster Visual Quality:**
   - Occasional "AI sheen" or illegible text
   - **Prompt Fix:** Better negative instructions, clearer layout specs

3. **Image Selection:**
   - Sometimes picks low-quality/irrelevant images
   - **Prompt Fix:** Strengthen OOH suitability criteria

---

## 📊 Data Transformations (Key Points)

### Scrape → Tier 1
```
Raw HTML → Markdown → 
Per-Page Snippets (services, team, process, value props) + 
Asset Candidates (text+image hooks)
```

### Tier 1 → Homepage Summary
```
All Page Summaries + Homepage Markdown → 
Single Business Profile (name, category, tone, value prop, differentiators)
```

### Summary + Tier 1 → Concepts
```
Business Profile + Page Evidence → 
3 Campaign Concepts (headline, angle, evidence, tone, CTA)
```

### Asset Candidates → Visual Pack
```
All Image URLs + Contexts → 
Curated Images (hero, product, texture) + 
Logos + Brand (colors, fonts, motifs)
```

### Concept + Visual Pack → Poster
```
1 Concept + All Images → 
5-6 Selected Images → 
DALL-E Prompt → 
Base64 PNG Image
```

---

## 🚀 Quick Start for Optimization

### Files to Focus On (Prompt Improvement)

**High Impact:**
1. `prompts/smb_generate_ad_concepts_system.txt` - Controls concept quality
2. `prompts/smb_generate_ad_concepts_user.txt` - Evidence grounding
3. `prompts/smb_poster_gen_system.txt` - Visual quality control
4. `prompts/smb_tier1_summarise_system.txt` - Extraction precision

**Medium Impact:**
5. `prompts/smb_image_hunt_system.txt` - Image curation quality
6. `prompts/smb_homepage_summarise_system.txt` - Business profile accuracy

**Low Impact (Working Well):**
7. `prompts/smb_image_selection_system.txt` - Already constrained
8. `prompts/smb_poster_gen_user.txt` - Template-driven

### Testing Strategy

1. **Unit Test:** Test single prompt pair with known input
2. **Integration Test:** Run full pipeline on sample URLs
3. **A/B Test:** Compare old vs new prompt outputs
4. **Monitor:** Track execution times + quality scores

### Key Metrics to Track

- **Speed:** Workflow execution time per stage
- **Quality:** Evidence grounding, message relevance, visual quality
- **Consistency:** Same input → similar output quality
- **Failure Rate:** How often workflows error out

---

## 🔧 Development Mode

### TEST vs LIVE Mode
- **TEST:** Uses `/webhook-test/` URLs (safe for iteration)
- **LIVE:** Uses `/webhook/` URLs (production)
- Toggle in UI or set `n8n_mode` session state

### Manual Re-run Buttons
- Each stage has a manual button in Results page
- Allows iterative refinement without full pipeline re-run
- Essential for prompt testing

### Debug Information
- All workflows return debug envelopes
- Stored in `*_debug` session state variables
- Viewable in "Developer diagnostics" expander

---

## 📁 Key Files for Another LLM to Review

**Essential:**
1. All 12 prompt files in `prompts/`
2. `backend/n8n_client.py` (lines 1-200) - API structure
3. `pages/02_results.py` (lines 350-600) - Workflow orchestration

**Helpful Context:**
4. This architecture document
5. `N8N_HTTP_MESSAGES_GUIDE.md` - Technical syntax reference

**Optional:**
6. Workflow JSON files (if deep n8n changes needed)

---

## 🎓 Glossary

- **OOH:** Out-of-Home advertising (billboards, posters, bus shelters)
- **Tier 1:** First-pass page-level analysis
- **Scrape Pack:** Complete scraped website data package
- **Asset Candidates:** High-value text/image hooks extracted during Tier 1
- **Visual Pack:** Curated brand assets (images, logos, colors, fonts)
- **Concept:** A complete campaign idea (headline, message, evidence, tone)
- **6-sheet / 48-sheet:** UK poster formats (portrait / landscape)

---

**Last Updated:** February 2026  
**Status:** Alpha - End-to-end functional, optimization in progress  
**Primary Optimization Goal:** Improve prompt quality → faster execution + higher relevance
