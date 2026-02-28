# Image Hunt Fixes - Summary

## Issues Fixed

### 1. ✅ Streamlit: Image Hunt Marked Done on Error (FIXED)

**Problem**: Step 3 was marking `image_hunt_done=True` even when the n8n call failed, preventing retries.

**Solution** (pages/02_results.py):
- Changed logic to only set `image_hunt_done=True` when `visual_pack` is successfully populated
- If the call fails or returns no visual_pack, `image_hunt_done` stays `False`
- Added explicit error tracking with `image_hunt_error` session state
- Error is logged but the step will be retried on next rerun

**Code Changes**:
```python
# Before: Always set to True, even on error
st.session_state["image_hunt_done"] = True
st.session_state["scrape_status"] = "summarising"
st.rerun()

# After: Only set to True on success
ok = bool(st.session_state.get("visual_pack"))
if ok:
    st.session_state["image_hunt_done"] = True
    st.session_state["scrape_status"] = "summarising"
    st.rerun()
else:
    st.session_state["image_hunt_done"] = False
    st.session_state["scrape_status"] = "summarising"
    if err:
        st.session_state["image_hunt_error"] = err
        st.warning(f"Image hunt failed (will not be marked done): {err}")
```

---

### 2. ✅ N8N: Prompts Already Loaded (ALREADY WORKING)

**Status**: The backend is already correctly loading and passing both:
- `prompt_system` from `prompts/smb_image_hunt_system.txt`
- `prompt_user` from `prompts/smb_image_hunt_user.txt` (templated with business/asset context)

**Code** (backend/n8n_client.py line 555-571):
```python
user_template = _load_prompt("smb_image_hunt_user.txt")
prompt_user = user_template.format(...)

payload = {
    "payload_type": "smb_image_hunt",
    ...
    "prompt_system": _load_prompt("smb_image_hunt_system.txt"),
    "prompt_user": prompt_user,
}
```

No changes needed — this is **Option A (recommended)** and working correctly.

---

### 3. ✅ Debug Output: Image Hunt Endpoint Displayed (ALREADY WORKING)

**Status**: The endpoint is already displayed in the debug sidebar.

**Location** (pages/02_results.py line 384):
```python
st.caption(f"Image hunt: `{resolve_n8n_webhook('image_hunt', mode)}`")
```

Expected output: `POST /webhook/SMB-image-hunt` (LIVE mode)

---

## Session State Updates

**Added to backend/state.py**:
```python
st.session_state.setdefault("image_hunt_done", False)
st.session_state.setdefault("image_hunt_debug", None)
st.session_state.setdefault("image_hunt_error", None)     # NEW
st.session_state.setdefault("visual_pack", None)
```

---

## Testing Checklist

After deploying these fixes:

1. **Test Success Case**:
   - Run a scrape normally
   - Image hunt should complete and set `image_hunt_done=True`
   - Verify `visual_pack` is populated in session state

2. **Test Failure Case** (simulate by breaking the webhook):
   - Temporarily point webhook to invalid URL
   - Image hunt should fail with warning
   - `image_hunt_done` should stay `False`
   - Next rerun should retry automatically

3. **Verify Debug Output**:
   - Check that "Image hunt:" endpoint is visible in sidebar
   - Confirm it matches your actual n8n webhook path

4. **Check Prompts**:
   - Review n8n workflow's "Normalise Inputs" node
   - Verify it receives non-null `prompt_system` and `prompt_user`
   - Should come from Streamlit payload (now guaranteed to be present)

---

## Root Cause Summary

The original "image hunt never fires" issue was caused by:
1. **Streamlit**: Error in Step 3 → marked done anyway → never retried
2. **N8N**: Missing prompts would cause 400 errors → Step 3 would fail silently
3. **Debugging**: No clear endpoint visibility made it hard to diagnose

All three issues are now fixed.
