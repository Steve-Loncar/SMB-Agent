"""
CSS Brand Extractor
-------------------
Fetches the homepage HTML and inline <style> blocks to extract:
  - Google Fonts families
  - Frequently-used non-standard hex colors (likely brand palette)
  - meta theme-color
  - og:image URL

Returns a dict that can be merged into business_summary["brand_visual"].
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Optional
from urllib.parse import urljoin

import requests

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    )
}

# WordPress Gutenberg / Block Editor default palette — these are not brand colors
_WP_PALETTE_NOISE = {
    "#FF6900", "#FCB900", "#7BDCB5", "#00D084", "#8ED1FC",
    "#0693E3", "#ABB8C3", "#EB144C", "#F78DA7", "#9B51E0",
    "#CF2E2E", "#007CBA", "#006BA1", "#005A87",
    "#1D2327",  # WP dark
}


def _hex3_to_hex6(h: str) -> str:
    """Expand 3-digit hex to 6-digit: #ABC → #AABBCC"""
    h = h.lstrip("#")
    if len(h) == 3:
        h = h[0]*2 + h[1]*2 + h[2]*2
    return "#" + h.upper()


def _is_grey(hex6: str) -> bool:
    """Returns True if a color is essentially achromatic (r≈g≈b within tolerance)."""
    h = hex6.lstrip("#")
    if len(h) != 6:
        return True
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    span = max(r, g, b) - min(r, g, b)
    return span < 20  # tight tolerance — only flag near-greys


def _classify_color_role(hex6: str) -> str:
    """Very rough role: accent | background | text"""
    h = hex6.lstrip("#")
    if len(h) != 6:
        return "accent"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    if luminance < 0.25:
        return "text"
    if luminance > 0.85:
        return "background"
    return "accent"


def extract_css_brand_cues(start_url: str, *, timeout_s: int = 12) -> dict:
    """
    Fetch the homepage and extract CSS brand cues from inline <style> blocks.

    Returns:
        {
          "fonts": ["Inter", ...],
          "colors": [
            {"hex": "#FFBE30", "role": "accent", "source": "inline_css", "frequency": 4},
            ...
          ],
          "og_image": "https://...",
          "theme_color": "#..."   # if present
        }
    """
    result: dict = {}

    try:
        resp = requests.get(start_url, headers=DEFAULT_HEADERS, timeout=timeout_s)
        resp.raise_for_status()
        html = resp.text
    except Exception:
        return result

    # ── Google Fonts ───────────────────────────────────────────────────────────
    raw_families = re.findall(r"family=([A-Za-z+:,@;0-9]+)", html)
    fonts: list[str] = []
    for raw in raw_families:
        # Each entry may be "Family+Name:wght@..." — take just the family name
        family = raw.split(":")[0].split(",")[0].replace("+", " ").strip()
        if family and family not in fonts:
            fonts.append(family)
    if fonts:
        result["fonts"] = fonts

    # ── Inline <style> blocks ─────────────────────────────────────────────────
    css_blocks = re.findall(r"<style[^>]*>(.*?)</style>", html, re.S)
    css_inline = "\n".join(css_blocks)

    # meta theme-color
    m_tc = re.search(
        r'<meta[^>]+name=["\']theme-color["\'][^>]+content=["\']([^"\']+)["\']', html, re.I
    ) or re.search(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']theme-color["\']', html, re.I
    )
    if m_tc:
        result["theme_color"] = m_tc.group(1).strip()

    # og:image
    m_og = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I
    ) or re.search(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.I
    )
    if m_og:
        result["og_image"] = m_og.group(1).strip()

    # ── Hex color frequency analysis ──────────────────────────────────────────
    # Identify colors that appear EXCLUSIVELY inside CSS variable declarations
    # for known infrastructure plugins (not brand-configurable ones).
    # We intentionally allow --mpev-* because site owners configure brand colors there.
    _INFRA_VAR_PREFIXES = (
        "--ag-", "--wc-", "--woo", "--jet-", "--elementor-",
        "--smcx-", "--cookie-", "--age-gate-", "--wp-admin",
    )
    # Count how many times each color appears in an infrastructure var declaration
    infra_var_counts: Counter = Counter()
    for m in re.finditer(r"(--.+?):\s*(#[0-9A-Fa-f]{3,6})\b", css_inline):
        var_name = m.group(1).strip()
        color = _hex3_to_hex6(m.group(2))
        if any(var_name.startswith(p) for p in _INFRA_VAR_PREFIXES):
            infra_var_counts[color] += 1

    raw_hex = re.findall(r"#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b", css_inline)
    normalised = [_hex3_to_hex6(h) for h in raw_hex]
    counts = Counter(normalised)

    brand_colors: list[dict] = []
    for hex6, freq in counts.most_common(50):
        if freq < 2:
            break  # only consider colors used at least twice
        if hex6 in _WP_PALETTE_NOISE:
            continue
        # Exclude only if ALL occurrences are from infrastructure plugin vars
        if infra_var_counts.get(hex6, 0) >= freq:
            continue
        if _is_grey(hex6):
            continue
        role = _classify_color_role(hex6)
        brand_colors.append({"hex": hex6, "role": role, "source": "inline_css", "frequency": freq})
        if len(brand_colors) >= 6:
            break

    if brand_colors:
        result["colors"] = brand_colors

    return result
