# 🔍 Why "No Images Available" & Image Hunt Flow

**Issue:** Getting "No images available for poster generation. Please run Global Image Hunt first."

**Status:** ✅ **FIXED with improved troubleshooting**

---

## 🌊 Complete Data Flow

```
Tier 1: Scrape Website
  ↓ outputs: homepage_markdown, page URLs, raw image URLs
  
Tier 2: Page Analysis (SMB_tier1_summariser)
  ├─ Extracts: page_summaries (snippets, services, value props)
  └─ GENERATES: asset_candidates (raw image URLs + basic metadata)
  
Tier 3a: Image Hunt (OPTIONAL but CRITICAL)
  ├─ Input: asset_candidates + business context
  ├─ Process: AI scores images for relevance, composition, OOH suitability
  └─ Output: visual_pack (enriched image objects with type, score, metadata)
  
Tier 3b: Poster Generation
  ├─ Input: visual_pack (enriched) OR asset_candidates (raw fallback)
  ├─ Process: LLM selects best images → generates poster prompt → generates image
  └─ Output: Final poster image
```

---

## ❌ Why This Error Happens

### Root Cause: Missing asset_candidates

The poster generation tries **in order**:
1. ✅ Use `visual_pack` (from Image Hunt) — IF it exists
2. ✅ Use `asset_candidates` (from Page Analysis) — IF it exists  
3. ❌ Show "No images available" — IF both are empty

This error occurs when **asset_candidates is empty**, which happens if:

### **Scenario A: Page Analysis Failed**
```
Scrape runs ✓
Page analysis runs ✗ (HTTP error, timeout, LLM error, bad schema response)
asset_candidates = [] (never populated)
Image Hunt button DISABLED (can't hunt with no candidates)
Poster gen FAILS (nothing to work with)
```

**Signs:**
- No "① Re-run Page Analysis" button shown
- or button shows but page_summaries are empty

**Fix:** Check tier1_summarise debug output, or manually click "① Re-run Page Analysis"

---

### **Scenario B: Page Analysis Succeeded but Found No Images**
```
Scrape runs ✓
Page analysis runs ✓
asset_candidates = [] (LLM extracted no useful images from pages)
Image Hunt button DISABLED (no candidates to enrich)
Poster gen FAILS
```

**Signs:**
- Page analysis completed successfully
- But Images carousel below shows empty
- "④ Global Image Hunt" button is grayed out

**Fix:** Some websites have poor image content. Try:
1. Different website, or
2. Manually extract image URLs if known

---

### **Scenario C: Image Hunt Didn't Run**
```
Scrape ✓
Page analysis ✓
asset_candidates = [image1, image2, ...]
Image Hunt button ENABLED
User clicks "④ Global Image Hunt" ✓ runs
visual_pack = [] (returned empty from n8n)
Poster gen FAILS
```

**Signs:**
- You can see the "④ Global Image Hunt" button enabled
- You clicked it (spinner appeared)
- But no images show up after completion

**Fix:** Check n8n Image Hunt workflow logs, or retry

---

## ✅ What Was Fixed

### New Feature: Auto-recovery button
If asset_candidates are missing after page analysis, you now get:
```
⚠️ No images were extracted during page analysis. Try re-running page analysis.
🔄 Re-run Page Analysis (Find Images)
```

This lets you retry without scrolling through the manual controls section.

### Improved Error Messages
Old message:
```
No images available for poster generation. Please run Global Image Hunt first.
```

New message:
```
⚠️ No images available for poster generation.

**How to fix:**
1. Click **④ Global Image Hunt** (scroll up to Manual Controls)
2. Then click **Generate Poster** again
```

---

## 🔄 Is Image Hunt Still Used?

**YES, Image Hunt is 100% still used and CRITICAL.**

### What Image Hunt Does

1. **Takes raw asset_candidates** from page analysis
   - These are bare URLs + basic text metadata (alt text, class names)

2. **Enriches them with AI analysis**
   - Assigns image type (product_closeup, people_portrait, environment, etc.)
   - Assigns recommended_use (background, hero_focal, supporting_detail)
   - Calculates composite_score (0-100 relevance)
   - Adds layout guidance, cropping notes
   - Filters out junk images (icons, tracking pixels, etc.)

3. **Produces visual_pack**
   - organized by category (product images, logos, environment, people)
   - metadata-rich objects that poster LLM can understand
   - scored and ranked for relevance to business

### Why Enrichment is Necessary

The **poster generation LLM needs structured metadata**:

```python
# What the poster LLM gets from Image Hunt:
{
    "url": "https://example.com/products/coffee.jpg",
    "type": "product_closeup",              # ← needs this
    "recommended_use": "hero_focal",        # ← needs this
    "why_relevant": "Shows final cup...",   # ← needs this
    "composite_score": 87,                  # ← uses this
    "cropping_guidance": "crop to 1:1",     # ← needs this
}

# Without Image Hunt, poster LLM only sees:
{
    "url": "https://example.com/products/coffee.jpg",
    "alt": "coffee cup",                    # generic, not structured
}
```

The structured metadata helps the LLM:
- Select **complementary images** (not just any images)
- Understand **format suitability** (portrait 6-sheet vs landscape 48-sheet)
- Make **composition-aware decisions** (where text will go)
- Respect **brand guidelines** (use logos vs product shots)

---

## 📋 Complete Flow Checklist

To successfully generate a poster:

1. ✅ **Scrape** — Home page → Enter URL → Apply
   - Wait for scrape to complete (1-2 min)
   - Confirm: "Scrape complete" message appears

2. ✅ **Page Analysis** — Auto-runs after scrape
   - Wait for: "Reviewing your key pages..." spinner
   - Confirm: Page analysis completed
   - Confirm: Images carousel shows > 0 images

3. ✅ **Image Hunt** — Manual button (crucial step!)
   - Click: "④ Global Image Hunt"
   - Wait: Spinner shows "Running image hunt…"
   - Confirm: Shows "Image hunt complete"
   - Confirm: Images carousel still shows images (enriched)

4. ✅ **Generate Poster** — On specific concept
   - Scroll to: "Campaign concepts" section
   - Click: "Generate Poster" on a concept
   - Wait: "Generating your poster..." spinner
   - Result: Poster image appears

---

## 🔧 Troubleshooting by Scenario

### "Page Analysis succeeded but found no images"
**Root Cause:** Website has poor image content or images are behind JavaScript

**Solutions:**
1. Try a different website with richer imagery
2. Manually add image URLs if you know them
3. Check page summaries to see what content was extracted

---

### "Image Hunt button is grayed out"
**Root Cause:** No asset_candidates generated from page analysis

**Solutions:**
1. Click new "🔄 Re-run Page Analysis (Find Images)" button
2. Check tier1_summarise debug output at bottom
3. Verify page analysis actually ran (check status indicator)

---

### "Clicked Image Hunt but no visual_pack appeared"
**Root Cause:** n8n Image Hunt workflow failed or returned empty

**Solutions:**
1. Check n8n console for execution logs
2. Look at "Debug: last image-hunt request/response" at bottom
3. Click "④ Global Image Hunt" again to retry

---

### "Ready to generate poster but got error 'No images available'"
**Root Cause:** All fallbacks failed
- visual_pack is empty (image hunt didn't work)
- asset_candidates are empty (page analysis didn't work)
- OR both exist but are malformed

**Solutions:**
1. Scroll up and click new error recovery button if shown
2. Check diagnostics section at bottom for detailed error
3. Start from scratch: click "🔄 Reset & start over"

---

## 📊 Data State Inspection

To debug which stage failed, scroll to **Developer diagnostics** at bottom and check:

**Tier1 Page Analysis Debug:**
- Look for "Debug: Tier1-summariser request/response"
- Check if `asset_candidates` field is present and non-empty
- If empty or missing, page analysis found no images

**Image Hunt Debug:**
- Look for "Debug: last image-hunt request/response"
- Check if n8n executed successfully (HTTP 200)
- Check if response includes `visual_pack` field
- If empty, enrichment didn't work

**Poster Generation Debug:**
- Look for "Debug: poster generation attempts"
- Check how many images were sent ("Images sent: X")
- Check HTTP status (should be 200)
- If error, read the error message

---

## ✅ Summary

| Question | Answer |
|----------|--------|
| Is Image Hunt still used? | ✅ **YES, 100% critical** |
| Is it optional? | ❌ **NO, required for good results** |
| Can you skip it? | ⚠️ **Only with fallback to raw asset_candidates (poor quality)** |
| When does it run? | Manually, when you click "④ Global Image Hunt" |
| What does it output? | Enriched `visual_pack` with scored, typed, categorized images |
| What if it's empty? | Poster generation falls back to raw asset_candidates (may fail) |

---

**TL;DR:** Image Hunt enriches raw image URLs into structured metadata. Without it, poster generation LLM doesn't have enough context to select complementary images. Current fix adds auto-recovery button when asset_candidates are missing.
