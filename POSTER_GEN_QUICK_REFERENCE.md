# Quick Reference: Poster Generation Fixes

## What Was Broken
Your "Generate Poster" button was failing inconsistently because:

1. ❌ **Missing `poster_concept`** in webhook payload → n8n can't see which concept to render
2. ❌ **Missing `guidelines`** in webhook payload → can't access brand colors/fonts
3. ❌ **Missing `business_summary`** in webhook payload → no business context for specificity  
4. ❌ **Poor error messages** → when failures occurred, you couldn't tell why
5. ❌ **No diagnostic UI** → no way to inspect what was sent/received

---

## What's Fixed
✅ Payload now includes all required fields  
✅ Error messages distinguish HTTP vs LLM vs parsing failures  
✅ Debug info stored in session and visible in UI  
✅ Comprehensive diagnostic section added  
✅ Full documentation provided  

---

## How to Verify It Works

### Shortest Test (3 minutes)
```
1. Home → Enter website URL → Apply
2. Wait for concepts (2-3 min)
3. Click "Generate Poster" on any concept
4. Watch for success or clear error message
```

### Debug If It Fails
```
1. Scroll to bottom of Results page
2. Expand "Debug: poster generation attempts"
3. See exact HTTP status, payload keys, image count, error message
4. Match against Common Failures section in POSTER_GEN_DEBUGGING.md
```

---

## Files Changed
- ✅ `backend/n8n_client.py` — added 3 payload fields
- ✅ `pages/02_results.py` — enhanced error handling + debug storage + diagnostic UI
- ✅ `POSTER_GEN_DEBUGGING.md` — new comprehensive guide
- ✅ `POSTER_GEN_FIXES_SUMMARY.md` — this summary

---

## Common Failures & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| "No images available" | Image hunt didn't run | Click "④ Global Image Hunt" button first |
| "Invalid poster concept" | Concept missing headline | Check SMB_generate_ad_concepts workflow output |
| "n8n HTTP 400" | Bad JSON in payload | Check that concept has all required fields |
| "Missing image_b64" | n8n response format changed | Update `call_n8n_generate_poster()` response parsing |
| "Failed to decode base64" | Corrupted image data | Check GPT-Image-1 API logs in n8n |

---

## Pre-Flight Checklist

Before running in production:
- [ ] Test one full end-to-end flow (URL → poster)
- [ ] Verify HTTP 200 in diagnostic output
- [ ] Check n8n execution logs for all 3 stages
- [ ] See at least one successful poster generated
- [ ] Verify error messages are clear if something fails

---

## Testing Commands

If you want to test directly in Python:
```python
from backend.n8n_client import call_n8n_generate_poster

result = call_n8n_generate_poster(
    poster_concept={
        "concept_name": "Test",
        "headline": "Premium Quality",
        "supporting_copy": "Locally sourced",
        "cta": "Learn more",
        "layout_notes": "Portrait 6-sheet",
        "image_idea": "Product shot",
    },
    guidelines={
        "business_name": "Test Business",
        "category": "Food",
        "tone": "premium",
        "value_proposition": "Best quality",
        "target_audience": "Affluent local",
        "brand_colors": [{"hex": "#2C3E50", "role": "primary"}],
    },
    visual_images=[
        {
            "url": "https://example.com/image.jpg",
            "type": "product_closeup",
            "recommended_use": "hero_focal",
            "why_relevant": "Shows quality",
        }
    ],
    business_summary={},
    mode="TEST",
)

print(f"OK: {result.get('ok')}")
print(f"HTTP: {result.get('status_code')}")
if result.get("_error"):
    print(f"Error: {result.get('_error')}")
```

---

## Where to Look for More Info

| Topic | File | Lines |
|-------|------|-------|
| Full issue explanation | POSTER_GEN_DEBUGGING.md | All sections |
| Payload construction | backend/n8n_client.py | 222-305 |
| Error handling | pages/02_results.py | 1348-1410 |
| Diagnostic UI | pages/02_results.py | 1465-1485 |
| n8n workflow structure | smb_image_gen.json | All (node connections) |

---

## Contact/Questions
For debugging assistance, check the diagnostic output first (scroll to bottom of Results page and expand "Debug: poster generation attempts").
