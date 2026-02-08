import streamlit as st
import os
import json
import requests

from backend.state import init_state


st.set_page_config(
    page_title="SMB Ad Agent (Alpha)",
    page_icon="🧩",
    layout="wide",
)

init_state()

st.title("🧩 SMB Ad Agent (Alpha)")
st.caption(
    "Basic alpha UI. Enter a business website, then review a generated description and ad poster concepts."
)

st.markdown(
    """
### How it works (alpha)
1. Paste a website URL
2. Click **Apply**
3. Review the output on the Results page
"""
)

st.info("Use the sidebar to navigate: **Home** → **Results**.", icon="ℹ️")

with st.expander("Dev notes", expanded=False):
    st.write(
        "- This is UI-only for now.\n"
        "- Next: wire scraping + n8n workflow trigger."
    )

# ------------------------------------------------------------
# V2 Step 1: Send scrape_pack payload to n8n (dev wiring helper)
# ------------------------------------------------------------

st.divider()
st.subheader("Dev: Scrape Pack payload (Step 1)")
st.caption(
    "This sends a small JSON payload to your n8n /scrape-pack webhook so you can wire nodes in test mode."
)

default_webhook = os.getenv("N8N_SCRAPE_PACK_WEBHOOK_URL", "")

with st.expander("Scrape Pack (Dev)", expanded=True):
    colA, colB = st.columns([2, 1], gap="large")

    with colA:
        webhook_url = st.text_input(
            "n8n scrape-pack webhook URL",
            value=default_webhook,
            help="Set env var N8N_SCRAPE_PACK_WEBHOOK_URL to avoid pasting this every time.",
            placeholder="https://<your-n8n>/webhook/scrape-pack",
        )

        website_url = st.text_input(
            "Website URL",
            value=st.session_state.get("website_url", ""),
            placeholder="https://example.co.uk",
        )

        depth = st.selectbox(
            "Depth",
            options=["homepage_only", "homepage_plus"],
            index=1,
            help="homepage_plus is intended to fetch homepage + a couple of likely About/Services pages.",
        )

        max_pages = st.number_input(
            "Max pages (only used for homepage_plus)",
            min_value=1,
            max_value=10,
            value=3,
            step=1,
        )

        payload = {
            "url": website_url.strip(),
            "depth": depth,
            "max_pages": int(max_pages),
        }

        st.markdown("**Payload preview (copy into n8n test mode):**")
        st.code(json.dumps(payload, indent=2), language="json")

        send = st.button("Send to n8n (scrape-pack)", type="primary", use_container_width=True)

    with colB:
        st.markdown("**Last run**")
        if "last_scrape_pack_status" in st.session_state:
            st.write("Status:", st.session_state["last_scrape_pack_status"])
        if "last_scrape_pack_error" in st.session_state:
            st.error(st.session_state["last_scrape_pack_error"])

    if send:
        st.session_state["website_url"] = website_url.strip()
        st.session_state["last_scrape_pack_payload"] = payload

        if not webhook_url.strip():
            st.session_state["last_scrape_pack_status"] = "not_sent"
            st.session_state["last_scrape_pack_error"] = "Missing n8n webhook URL."
            st.stop()

        if not payload["url"]:
            st.session_state["last_scrape_pack_status"] = "not_sent"
            st.session_state["last_scrape_pack_error"] = "Missing website URL."
            st.stop()

        try:
            resp = requests.post(webhook_url.strip(), json=payload, timeout=60)
            st.session_state["last_scrape_pack_status"] = f"{resp.status_code}"
            st.session_state["last_scrape_pack_error"] = ""

            # Try JSON first; fall back to raw text
            try:
                data = resp.json()
                st.session_state["last_scrape_pack_response"] = data
                st.success(f"Sent ✓ ({resp.status_code})")
                st.markdown("**Response (JSON):**")
                st.code(json.dumps(data, indent=2), language="json")
            except Exception:
                st.session_state["last_scrape_pack_response"] = resp.text
                st.warning(f"Sent ✓ ({resp.status_code}) but response was not JSON.")
                st.markdown("**Response (raw):**")
                st.code(resp.text)
        except requests.RequestException as e:
            st.session_state["last_scrape_pack_status"] = "error"
            st.session_state["last_scrape_pack_error"] = str(e)
            st.error(f"Request failed: {e}")

