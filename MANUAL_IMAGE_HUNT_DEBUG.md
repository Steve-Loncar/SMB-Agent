# Manual Image Hunt Debug Guide

## Quick Start

You already have a **"Run Image Hunt"** button in the sidebar! Here's how to use it:

### Prerequisites
Before running manual image hunt, you need the following in session state:
1. **asset_candidates** - List of image URLs from the website
2. **business_summary** - Business info (name, category, etc.)
3. **tier1_page_summaries** - Text snippets from tier 1 pages
4. **tier2_page_summaries** (optional) - Text snippets from tier 2 pages

The button is **disabled** until `asset_candidates` is populated.

### Workflow

1. **Run a normal scrape** to completion through "Run AI 2nd pass (text blobs)" 
   - This populates asset_candidates and business_summary
   - "Run Image Hunt" button becomes enabled

2. **Click "Run Image Hunt"** button in the sidebar
   - Spinner shows "Reviewing images..."
   - On success: Shows success message + marks `image_hunt_done=True`
   - On failure: Shows error message + keeps `image_hunt_done=False` (retryable)

3. **Iterate on the workflow**
   - Make changes to your SMB_Image_hunt.json in n8n
   - Click "Run Image Hunt" again to test
   - No need to re-run scrape or prior steps!

4. **Debug the request/response**
   - Scroll to bottom → "Developer diagnostics"
   - Expand → "Debug: image-hunt request/response"
   - View:
     - Webhook URL being called
     - HTTP status & final URL
     - Prompts being sent (system + user)
     - Asset candidates count
     - N8N response JSON

### Error Troubleshooting

If image hunt fails:

1. **Check the webhook endpoint**
   - Should be: `/webhook/SMB-image-hunt` (LIVE mode) or `/webhook-test/SMB-image-hunt` (TEST)
   - View in sidebar under "Image hunt: `...`"

2. **Check the prompts in debug output**
   - "Payload sent (prompts + assets)"
   - Verify `prompt_system` and `prompt_user` are not empty

3. **Check n8n error logs**
   - Go to your n8n instance
   - Open SMB_Image_hunt workflow
   - Check Webhook node → Output for any errors

4. **Check the response**
   - Look for `_error` field in debug output
   - Review "N8N response JSON" section

### Session State Reset

If you get stuck, click **"Reset"** button to clear everything and start fresh.

This preserves `target_url` for convenience, so you can immediately re-scrape without re-entering the URL.

### Manual State Editing (Advanced)

If you want to test with stale/modified session state:

1. Open browser dev console (F12)
2. Check Streamlit session state in Network tab
3. Or use Streamlit's built-in session_state viewer if available

## Example: Iterating on Image Hunt Prompts

1. ✅ Run normal scrape to get asset_candidates
2. ✅ Edit prompts/smb_image_hunt_system.txt or prompts/smb_image_hunt_user.txt
3. ✅ Push changes to n8n (via n8n VSCode extension)
4. ✅ Click "Run Image Hunt" button
5. ✅ Check debug output
6. ✅ If still broken: repeat 2-5
7. ✅ Once working: run full scrape to verify end-to-end

## Files Involved

- **UI Logic**: pages/02_results.py (manual button + debug output)
- **API Call**: backend/n8n_client.py (call_n8n_image_hunt function)
- **Prompts**: prompts/smb_image_hunt_system.txt, prompts/smb_image_hunt_user.txt
- **State**: backend/state.py (session_state defaults)
- **Workflow**: workflows/fpgconsulting_cloud_steve_l/my_project/SMB_Image_hunt.json

## Changes Made (This Session)

✅ Manual button now uses success-only logic (like auto-run)
✅ Added `image_hunt_error` to session state tracking
✅ Added debug request/response section in diagnostics
✅ Payload display includes readable counts (not full lists)
✅ Clear error messages on failure
