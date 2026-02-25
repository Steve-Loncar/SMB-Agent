# 🔧 Image Hunt Pipeline - Technical Reference

Quick lookup for developers maintaining the image generation pipeline.

---

## 🗂️ File Structure

```
SMB-Agent/
├── backend/
│   ├── n8n_client.py          # Webhook communication (3 poster funcs)
│   ├── state.py               # Session state initialization
│   ├── scraper.py             # Website scraping
│   └── image_gen.py           # (Legacy? Check if still used)
├── pages/
│   ├── 01_home.py             # URL input, scrape trigger
│   └── 02_results.py          # MAIN: Pipeline orchestration (1,513 lines)
├── prompts/
│   ├── smb_tier1_summarise_system.txt    # Page analysis LLM
│   ├── smb_image_hunt_system.txt         # Image enrichment LLM
│   ├── smb_poster_gen_system.txt         # Poster generation LLM
│   └── ... (12 more prompts for other features)
├── workflows/fpgconsulting_cloud_steve_l/my_project/
│   ├── SMB_tier1_summariser.json         # Stage 1: Page analysis
│   ├── SMB_Image_hunt.json               # Stage 2: Image enrichment
│   ├── smb_image_gen.json                # Stage 3: Poster generation
│   └── ... (15 more workflows)
└── requirements.txt
```

---

## 🔌 n8n Webhook Paths

```python
# In backend/n8n_client.py (lines 30-40)

N8N_WEBHOOK_PATHS = {
    "tier1_summarise": "https://cloud.n8n.io/webhook/smb-tier1-page-analysis",
    "image_hunt": "https://cloud.n8n.io/webhook/smb-image-hunt",
    "generate_image": "https://cloud.n8n.io/webhook/smb-image-generation",
    "generate_ad_concepts": "...",
    "generate_ads": "...",
    # etc.
}
```

### When Each is Called:

| Function | Webhook | Payload |
|----------|---------|---------|
| `call_n8n_tier1_summarise()` | `/smb-tier1-page-analysis` | `{scrape_result}` |
| `call_n8n_image_hunt()` | `/smb-image-hunt` | `{asset_candidates, business_summary}` |
| `call_n8n_generate_poster()` | `/smb-image-generation` | `{poster_concept, guidelines, poster_visual_images, business_summary}` |

---

## 💾 Key Data Structures

### asset_candidates (From tier1_summariser)

```python
# pages/02_results.py, line ~920
st.session_state["asset_candidates"] = [
    {
        "url": "https://website.com/images/product.jpg",
        "alt": "Product shot",
        "context": "Homepage hero section",
        "source": "page_analysis"
    },
    # ... 10-100 more URLs
]
```

**Location in code:** [pages/02_results.py#L915](pages/02_results.py#L915)  
**Populated by:** tier1_summariser webhook response  
**Used by:** Image Hunt input + fallback for poster generation

---

### visual_pack (From image_hunt)

```python
# pages/02_results.py, line ~1090
st.session_state["visual_pack"] = {
    "product_images": [
        {
            "url": "https://website.com/images/product.jpg",
            "type": "product_closeup",
            "recommended_use": "hero_focal",
            "why_relevant": "Shows product details clearly",
            "composite_score": 92,
            "cropping_guidance": "No cropping needed",
            "layout_zone": "center",
            "filter_suggestions": ["none"],
            "text_safe_margin": 20
        },
        # ... more product images
    ],
    "people_images": [...],
    "environment_images": [...],
    "logo_variants": [...]
}
```

**Location in code:** [pages/02_results.py#L1090](pages/02_results.py#L1090)  
**Populated by:** image_hunt webhook response  
**Used by:** poster_visual_images selection + poster generation

---

### poster_visual_images (For poster generation)

```python
# pages/02_results.py, lines 1280-1325
poster_visual_images = {
    "primary_image": {
        "url": "...",
        "type": "product_closeup",
        "size": "large"
    },
    "secondary_images": [
        {"url": "...", "type": "people_portrait", "size": "medium"},
        {"url": "...", "type": "environment", "size": "small"}
    ],
    "logo": {"url": "...", "type": "logo"}
}

# If visual_pack empty, falls back to asset_candidates
if not visual_pack and asset_candidates:
    poster_visual_images["primary_image"] = {"url": asset_candidates[0]["url"]}
    poster_visual_images["secondary_images"] = [
        {"url": c["url"]} for c in asset_candidates[1:5]
    ]
```

**Key point:** If `visual_pack` is empty but `asset_candidates` exist, poster uses raw URLs (lower quality but works)

---

## 🔄 Execution Flow (In Detail)

### Step 1: User enters URL and clicks "Apply"

```python
# pages/01_home.py
# Calls: backend.scraper.scrape_website(url)
# Triggers: pages/02_results.py auto-run

st.session_state["scrape_result"] = {
    "homepage_markdown": "...",
    "page_urls": [...],
    "raw_html_snippets": {...}
}
```

### Step 2: page Analysis Auto-Runs

```python
# pages/02_results.py, lines 880-920
if st.session_state["scrape_done"] and not st.session_state["tier1_summarise_done"]:
    
    # Call n8n tier1_summariser
    response = call_n8n_tier1_summarise(
        business_context=st.session_state["business_context"],
        pages=st.session_state["scrape_result"],
        # ... other params
    )
    
    # Extract results
    st.session_state["page_summaries"] = response["page_summaries"]
    st.session_state["asset_candidates"] = response.get("asset_candidates", [])
    st.session_state["tier1_summarise_done"] = True
    st.rerun()
```

**Location:** [pages/02_results.py#L880-L920](pages/02_results.py#L880-L920)

### Step 3: Image Hunt Available?

```python
# pages/02_results.py, lines 500-552
can_run_image_hunt = (
    len(st.session_state.get("asset_candidates", [])) > 0
    and st.session_state.get("tier1_summarise_done")
)

if not can_run_image_hunt and st.session_state.get("tier1_summarise_done"):
    st.warning("⚠️ No images were extracted...")
    if st.button("🔄 Re-run Page Analysis (Find Images)"):
        st.session_state["tier1_summarise_done"] = False
        st.rerun()
```

**Location:** [pages/02_results.py#L500-L552](pages/02_results.py#L500-L552)

### Step 4: User Clicks Global Image Hunt

```python
# pages/02_results.py, lines 520-580 (manual controls)
if can_run_image_hunt:
    if st.button("④ Global Image Hunt", use_container_width=True):
        with st.spinner("Running image hunt..."):
            response = call_n8n_image_hunt(
                business_summary=st.session_state["business_summary"],
                asset_candidates=st.session_state["asset_candidates"],
                guidelines=st.session_state["guidelines"]
            )
            st.session_state["visual_pack"] = response.get("visual_pack", {})
            st.success(f"✅ Image hunt complete: {count_images(visual_pack)} images curated")
            st.rerun()
```

**Location:** [pages/02_results.py#L520-L580](pages/02_results.py#L520-L580)

### Step 5: User Clicks Generate Poster

```python
# pages/02_results.py, lines 1200-1350
# (Happens in campaign concepts section)

if st.button("Generate Poster", key=f"poster_{concept_id}"):
    
    # Build poster_visual_images (from visual_pack or fallback)
    poster_visual_images = build_poster_visual_images(
        visual_pack=st.session_state.get("visual_pack", {}),
        asset_candidates=st.session_state.get("asset_candidates", [])
    )
    
    if not poster_visual_images:
        st.error("⚠️ No images available for poster generation...")
        show_recovery_steps()
        return
    
    # Call n8n poster generation
    response = call_n8n_generate_poster(
        poster_concept=concept,
        guidelines=st.session_state["guidelines"],
        business_summary=st.session_state["business_summary"],
        poster_visual_images=poster_visual_images
    )
    
    # Display results
    st.image(response["image_urls"], captions=[...])
```

**Location:** [pages/02_results.py#L1200-L1350](pages/02_results.py#L1200-L1350)

---

## 🐛 Debugging Checklist

### "asset_candidates is empty"

```python
# Check 1: Did tier1_summariser run?
assert st.session_state.get("tier1_summarise_done") == True

# Check 2: Did it return asset_candidates?
assert len(st.session_state.get("asset_candidates", [])) > 0

# Check 3: Check the response
print(st.session_state.get("tier1_summarise_response"))
```

**If Check 1 fails:** Page analysis didn't run (click recovery button)  
**If Check 2 fails:** Page analysis found no images (try different website)  
**If Check 3 shows error:** Check n8n tier1 workflow logs

---

### "visual_pack is empty"

```python
# Check 1: Did image hunt run?
assert st.session_state.get("image_hunt_run") == True

# Check 2: Did it return visual_pack?
assert len(st.session_state.get("visual_pack", {})) > 0

# Check 3: Check the response
print(st.session_state.get("image_hunt_response"))
```

**If Check 1 fails:** User didn't click image hunt button  
**If Check 2 fails:** Image hunt found no suitable images (rare)  
**If Check 3 shows error:** Check n8n image_hunt workflow logs

---

### "Poster generation failed"

```python
# Check 1: Did we have images for it?
poster_visual_images = st.session_state.get("poster_visual_images")
assert len(poster_visual_images) > 0

# Check 2: Was payload complete?
payload = {
    "poster_concept": str,       # must exist
    "guidelines": str,           # must exist
    "business_summary": str,     # must exist
    "poster_visual_images": dict # must exist and have images
}

# Check 3: Check response
print(st.session_state.get("poster_generation_response"))
```

**Common issues:**
- `poster_concept` missing → fix in payload building
- `guidelines` missing → fix in payload building
- `poster_visual_images` empty → fallback failed (check earlier steps)
- n8n error → check image-selection, prompt-gen, or image-render nodes

---

## 📊 Session State Variables

Key variables in `st.session_state`:

```python
{
    # From scraper
    "scrape_result": {...},
    "scrape_done": bool,
    
    # From tier1_summariser (page analysis)
    "page_summaries": {...},
    "asset_candidates": [{...}],           # ← CRITICAL
    "tier1_summarise_done": bool,
    "tier1_summarise_response": {...},
    
    # From image_hunt
    "visual_pack": {...},                  # ← CRITICAL
    "image_hunt_run": bool,
    "image_hunt_response": {...},
    
    # For poster generation
    "campaigns": [...],
    "poster_concepts": [...],
    "poster_visual_images": {...},
    "poster_generation_response": {...},
    
    # Business context
    "business_summary": str,
    "guidelines": str,
    "business_context": {...}
}
```

---

## 🚨 Common Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| "asset_candidates is empty" | tier1 failed or found no images | Click recovery button / try different URL |
| "visual_pack is empty" | image_hunt failed or skipped | Click "④ Global Image Hunt" button |
| "No images available for poster" | Both asset_candidates AND visual_pack empty | Scroll to recovery button and follow steps |
| HTTP 500 from n8n | Workflow error | Check n8n cloud console logs |
| HTTP 401 from n8n | Auth failed | Check webhook URL and API keys |
| "Cannot find node 'Send Image to Poster'" | n8n workflow disconnected | Verify workflow connections in n8n UI |
| Timeout on tier1_summariser | Large number of pages | Reduce number of pages to analyze |

---

## 🔍 Response Structures

### tier1_summariser Response

```json
{
    "success": true,
    "page_summaries": {
        "https://example.com/products": {
            "title": "Products",
            "summary": "Our product offerings...",
            "key_points": ["point1", "point2"],
            "images_found": 15,
            "has_testimonials": false
        }
    },
    "asset_candidates": [
        {
            "url": "https://cdn.example.com/product.jpg",
            "alt": "Product image",
            "context": "Product listing page",
            "source": "img tag"
        }
    ],
    "business_insights": {
        "primary_services": ["service1", "service2"],
        "target_audience": "description"
    }
}
```

### image_hunt Response

```json
{
    "success": true,
    "visual_pack": {
        "product_images": [
            {
                "url": "https://cdn.example.com/product.jpg",
                "type": "product_closeup",
                "recommended_use": "hero_focal",
                "why_relevant": "Shows product in detail",
                "composite_score": 92,
                "cropping_guidance": "No cropping needed",
                "layout_zone": "center",
                "filter_suggestions": ["contrast_boost"],
                "text_safe_margin": 20
            }
        ],
        "people_images": [...],
        "environment_images": [...],
        "logo_variants": [...]
    },
    "scoring_methodology": "..."
}
```

### poster_generation Response

```json
{
    "success": true,
    "image_urls": [
        "https://temp-cdn.example.com/poster_1.png",
        "https://temp-cdn.example.com/poster_2.png",
        "https://temp-cdn.example.com/poster_3.png"
    ],
    "captions": [
        "Version 1: Modern design",
        "Version 2: Bold typography",
        "Version 3: Image-focused"
    ],
    "metadata": {
        "prompt_used": "...",
        "generation_time_ms": 3400,
        "model": "dall-e-3"
    }
}
```

---

## 🎯 Key Functions

### In backend/n8n_client.py:

```python
def call_n8n_tier1_summarise(business_context, pages, **kwargs):
    """
    Analyzes website pages, extracts images and insights
    Returns: page_summaries, asset_candidates
    """

def call_n8n_image_hunt(business_summary, asset_candidates, guidelines):
    """
    Enriches asset_candidates with AI scoring
    Returns: visual_pack (categorized, scored images)
    """

def call_n8n_generate_poster(poster_concept, guidelines, business_summary, poster_visual_images):
    """
    Generates 3 poster variations
    Returns: image_urls (DALL-E generated images)
    """
```

### In pages/02_results.py:

```python
def build_poster_visual_images(visual_pack, asset_candidates):
    """
    Selects images for poster generation
    Priority: visual_pack → asset_candidates → None
    """

def validate_image_availability():
    """
    Checks if poster generation is possible
    Returns: (can_generate: bool, error_message: str)
    """

def show_recovery_steps():
    """
    Shows "No images available" error with recovery button
    """
```

---

## 📝 Maintenance Notes

### When Adding New Image Sources:
1. Update tier1_summariser prompt to extract from new sources
2. Update image_hunt prompt to handle new image types
3. Test with multiple websites
4. Check if visual_pack structure needs to change

### When Modifying n8n Workflows:
1. Update webhook path in n8n_client.py if changed
2. Test with payload examples in debug section
3. Verify response schema matches code expectations
4. Check for breaking changes in field names

### When Updating Prompts:
1. Edit files in `prompts/` directory
2. Don't change prompt variable names in n8n workflows
3. Test with tier1_prompt_test, image_hunt_test locally first
4. Verify n8n workflow picks up new prompts (may need refresh)

---

## 📚 Related Documentation

- [IMAGE_HUNT_FLOW_ANALYSIS.md](IMAGE_HUNT_FLOW_ANALYSIS.md) — Complete flow explanation
- [IMAGE_HUNT_COMPLETE_SYSTEM.md](IMAGE_HUNT_COMPLETE_SYSTEM.md) — System overview
- [POSTER_GEN_DEBUGGING.md](POSTER_GEN_DEBUGGING.md) — Detailed debugging guide
- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) — Overall app architecture
