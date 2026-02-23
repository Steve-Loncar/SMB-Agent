# n8n smb_image_gen.json — Upgrade Instructions
## gpt-image-1 + Vision for Stage 5B/5C

These are the exact changes to make in the `smb_image_gen` workflow in n8n.
All node names reference the current workflow.

---

## CHANGE 1 — "Normalise Inputs" (Set node)

Add one new assignment to read the enriched image objects from the payload:

| Field | Value |
|-------|-------|
| Name  | `visual_images` |
| Value | `={{ $json.body.visual_images }}` |
| Type  | `Array` |

Keep all existing assignments. This just adds the enriched objects alongside the existing `image_urls` fallback.

---

## CHANGE 2 — "OpenAI: Select best images" (HTTP Request node)

The `image_selection_user_template` arrives pre-filled (Python already substituted `{visual_images}`, `{poster_concept}`, `{guidelines}`).

Replace the current `messages` expression with a simplified version that removes redundant data appending:

**Current (remove):**
```javascript
={{[
  {
    role: 'system',
    content: ($json.image_selection_system)
  },
  {
    role: 'user',
    content:
      ($json.image_selection_user_template) +
      '\n\n===== DATA INPUTS =====\n\n' +
      'POSTER CONCEPT:\n' +
      JSON.stringify($json.poster_concept) +
      '\n\nGUIDELINES:\n' +
      JSON.stringify($json.guidelines) +
      '\n\nIMAGE URLS:\n' +
      JSON.stringify($json.image_urls)
  }
]}}
```

**New:**
```javascript
={{[
  {
    role: 'system',
    content: $json.image_selection_system
  },
  {
    role: 'user',
    content: $json.image_selection_user_template
  }
]}}
```

Rationale: the template already has all data embedded by Python. Appending it again was doubling the token count and sending the old `image_urls` (bare strings) instead of the enriched `visual_images` objects.

---

## CHANGE 3 — "Build Stage 2 Prompt" (Code node)

The code node needs to:
1. Extract `hero_image_url` from selection_notes (new field)
2. Substitute the user prompt template correctly (same as before)
3. Output `hero_image_url` so the next node can use it as a vision input

**Replace the jsCode with:**
```javascript
const inputs = $('Normalise Inputs').item.json;
const parsed = $json.parsed || {};
const selectionNotes = parsed.selection_notes || {};
const selectedImages = parsed.selected_images || [];

// Extract hero image URL for vision input
const heroImageUrl = selectionNotes.hero_image_url ||
  (selectedImages.length > 0
    ? (typeof selectedImages[0] === 'string' ? selectedImages[0] : selectedImages[0].url)
    : '');

// Build selected_images as simple URL array for backwards compat
const selectedImageUrls = selectedImages.map(im =>
  typeof im === 'string' ? im : (im.url || '')
).filter(Boolean);

let userPrompt = inputs.poster_gen_user_template || '';
userPrompt = userPrompt.split('{poster_concept}').join(
  JSON.stringify(inputs.poster_concept, null, 2)
);
userPrompt = userPrompt.split('{selected_images}').join(
  JSON.stringify(parsed, null, 2)   // pass full parsed object (includes selection_notes.hero_image_url)
);
userPrompt = userPrompt.split('{guidelines}').join(
  JSON.stringify(inputs.guidelines, null, 2)
);

return [{
  json: {
    system_prompt_poster: inputs.poster_gen_system,
    user_prompt_poster: userPrompt,
    hero_image_url: heroImageUrl,
    selected_images: selectedImageUrls,
    selection_notes: selectionNotes,
  }
}];
```

---

## CHANGE 4 — "Generate Poster Prompt" (HTTP Request node)
### Make gpt-4o SEE the hero image (vision input)

This is the key change that makes the poster brief grounded in the actual website photography.

**Current messages expression:**
```javascript
={{ [ { "role": "system", "content": $json.system_prompt_poster }, { "role": "user", "content": $json.user_prompt_poster } ] }}
```

**New messages expression:**
```javascript
={{[
  {
    role: "system",
    content: $json.system_prompt_poster
  },
  {
    role: "user",
    content: [
      {
        type: "image_url",
        image_url: {
          url: $json.hero_image_url,
          detail: "high"
        }
      },
      {
        type: "text",
        text: $json.user_prompt_poster
      }
    ]
  }
]}}
```

**Why:** gpt-4o will now actually SEE the Ginger Pig hero image (or whatever the client's best photo is) before writing the poster prompt. The prompt it produces will describe real lighting, real colours, real composition — not generic stock photo descriptions.

**Note:** If `hero_image_url` is empty or unreachable, gpt-4o will still produce a text-only prompt. Add a fallback check if needed.

Keep `model: gpt-4o` — this is still a chat completions call, just with vision enabled.

---

## CHANGE 5 — "Build Stage 3 Prompt" (Code node)

Add format-aware size selection so portrait vs landscape is reflected in the gpt-image-1 call.

**Replace jsCode with:**
```javascript
const parsed = JSON.parse($json.no_fences);
const selectedImages = $('Build Stage 2 Prompt').item.json.selected_images || [];
const selectionNotes = $('Build Stage 2 Prompt').item.json.selection_notes || {};
const overlay_text = parsed.render_notes?.text_overlay || {};
const text_safe_area = parsed.render_notes?.text_safe_area || "Leave generous clean space for text overlay.";

const render_notes = {
  overlay_text,
  text_safe_area,
  negative_instructions: parsed.render_notes?.negative_instructions
};

// Format-aware size for gpt-image-1
const orientation = parsed.layout_spec?.orientation || 'portrait';
const imageSize = orientation === 'landscape' ? '1536x1024' : '1024x1536';

let poster_prompt = parsed.poster_prompt || '';
poster_prompt += `\n\nCRITICAL: Do NOT include any text, letters, numbers, signage, labels, badges, seals, or typography. Background plate only. ${text_safe_area}`;

return [{
  json: {
    poster_prompt,
    image_size: imageSize,
    poster_metadata: parsed,
    selected_images: selectedImages,
    selection_notes: selectionNotes,
    render_notes,
  }
}];
```

---

## CHANGE 6 — "DALL-E - Generate Poster Image" (HTTP Request node)
### Switch to gpt-image-1

**Rename node to:** `gpt-image-1 — Generate Poster Image`

**URL:** Keep `https://api.openai.com/v1/images/generations` (same endpoint)

**Body parameters — replace all existing with:**

| Parameter | Value |
|-----------|-------|
| `model` | `gpt-image-1` |
| `prompt` | `={{ $('Build Stage 3 Prompt').item.json.poster_prompt }}` |
| `n` | `1` |
| `size` | `={{ $('Build Stage 3 Prompt').item.json.image_size }}` |
| `quality` | `high` |
| `output_format` | `png` |

**Remove:** `response_format: b64_json` — gpt-image-1 returns base64 PNG automatically.

**Response parsing:** gpt-image-1 returns `data[0].b64_json` — same path as DALL-E 3. The "Step 9: Prepare Response Payload" node (`$json.data[0].b64_json`) should work unchanged.

**If you get a 400/422 error on `output_format`:** Remove that parameter — it may not be required. The model defaults to PNG with base64.

---

## CHANGE 7 — "Step 9: Prepare Response Payload" (Set node)

No change needed. `$json.data[0].b64_json` works the same for gpt-image-1.

---

## Summary of data flow after changes

```
Webhook
  → Normalise Inputs       [reads: visual_images (new), image_urls, all prompts]
  → OpenAI: Select Images  [gpt-4o | enriched image objects → selects 5-6 + nominates hero]
  → Raw text in → Strip fences → Parse JSON
  → Build Stage 2 Prompt   [extracts hero_image_url, builds user prompt]
  → Generate Poster Prompt [gpt-4o VISION: sees hero image + prompt → writes gpt-image-1 brief]
  → Raw text in1 → Strip fences1
  → Build Stage 3 Prompt   [finalises prompt, sets size from orientation]
  → gpt-image-1 Generate   [text + hero image brief → real poster background plate]
  → Step 9: Prepare Response
  → Step 10: Respond to Webhook
```

---

## Future enhancement: gpt-image-1 Edit endpoint

For an even stronger result, replace Stage 5C with the **edit endpoint** which uses the actual hero image as the base:

```
POST /v1/images/edits
model: gpt-image-1
image: [binary of hero image]
prompt: [poster_prompt]
size: 1024x1536
```

This requires two new nodes before the generation step:
1. **HTTP Request "Download Hero Image"**: GET `$('Build Stage 2 Prompt').item.json.hero_image_url` with Response Format = File (binary)
2. **HTTP Request "gpt-image-1 Edit"**: POST to `/v1/images/edits`, Body Type = Form-Data (Multipart), with `image` field pointing to binary from step 1

This guarantees the output is a transformation of the real client photograph, not a new AI-generated image.
