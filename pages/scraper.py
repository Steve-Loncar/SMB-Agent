from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class ScrapeResult:
    start_url: str
    visited_urls: list[str]
    text: str
    image_urls: list[str]


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    )
}


def _same_domain(a: str, b: str) -> bool:
    try:
        pa = urlparse(a)
        pb = urlparse(b)
        return (pa.netloc or "").lower() == (pb.netloc or "").lower()
    except Exception:
        return False


def _clean_text(text: str) -> str:
    # Collapse whitespace, remove very short lines, keep it readable
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 30:
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    return cleaned


def _extract_visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    # remove non-content elements
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    # Prefer main/article if present
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(separator="\n")
    return _clean_text(text)


def _extract_images(html: str, base_url: str, max_images: int) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    urls: list[str] = []

    # Basic: pull <img src> plus some common lazy-load attrs
    candidates = []
    for img in soup.find_all("img"):
        src = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-lazy-src")
            or img.get("data-original")
        )
        if not src:
            continue
        candidates.append(src)

    def norm(u: str) -> str | None:
        u = u.strip()
        if not u:
            return None
        abs_u = urljoin(base_url, u)
        if abs_u.startswith("data:"):
            return None
        # Keep http(s) only
        if not abs_u.startswith("http://") and not abs_u.startswith("https://"):
            return None
        return abs_u

    seen = set()
    for c in candidates:
        nu = norm(c)
        if not nu or nu in seen:
            continue
        seen.add(nu)
        urls.append(nu)
        if len(urls) >= max_images:
            break

    return urls


def _extract_internal_links(html: str, base_url: str, max_links: int) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    start = base_url
    start_parsed = urlparse(start)
    out: list[str] = []
    seen = set()

    for a in soup.find_all("a"):
        href = a.get("href")
        if not href:
            continue
        href = href.strip()
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue

        abs_u = urljoin(base_url, href)
        parsed = urlparse(abs_u)
        if parsed.scheme not in ("http", "https"):
            continue

        # same domain only
        if (parsed.netloc or "").lower() != (start_parsed.netloc or "").lower():
            continue

        # ignore obvious non-pages
        if re.search(r"\.(pdf|jpg|jpeg|png|gif|webp|svg|zip|mp4|mov|avi)(\?|$)", parsed.path, re.I):
            continue

        # strip fragments
        abs_u = abs_u.split("#")[0]
        if abs_u in seen:
            continue

        seen.add(abs_u)
        out.append(abs_u)
        if len(out) >= max_links:
            break

    return out


def fetch_html(url: str, timeout_s: int = 15) -> str:
    r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout_s)
    r.raise_for_status()
    # best-effort decode
    r.encoding = r.encoding or "utf-8"
    return r.text


def scrape_site(
    start_url: str,
    *,
    max_pages: int = 3,
    max_internal_links_from_home: int = 8,
    max_images_total: int = 12,
    timeout_s: int = 15,
) -> ScrapeResult:
    """
    Basic alpha scraper:
    - Fetch home
    - Optionally crawl a small number of internal links (same domain) up to max_pages
    - Extract visible text + images (best effort)
    """
    visited: list[str] = []
    all_text_parts: list[str] = []
    all_images: list[str] = []
    seen_images = set()

    # Home
    home_html = fetch_html(start_url, timeout_s=timeout_s)
    visited.append(start_url)
    home_text = _extract_visible_text(home_html)
    if home_text:
        all_text_parts.append(f"[PAGE] {start_url}\n{home_text}")

    for u in _extract_images(home_html, start_url, max_images=max_images_total):
        if u not in seen_images:
            seen_images.add(u)
            all_images.append(u)
            if len(all_images) >= max_images_total:
                break

    # Crawl a few internal links
    if max_pages > 1:
        links = _extract_internal_links(home_html, start_url, max_links=max_internal_links_from_home)
        for link in links:
            if len(visited) >= max_pages:
                break
            if not _same_domain(start_url, link):
                continue
            try:
                html = fetch_html(link, timeout_s=timeout_s)
            except Exception:
                continue
            visited.append(link)

            t = _extract_visible_text(html)
            if t:
                all_text_parts.append(f"[PAGE] {link}\n{t}")

            if len(all_images) < max_images_total:
                for u in _extract_images(html, link, max_images=max_images_total):
                    if u not in seen_images:
                        seen_images.add(u)
                        all_images.append(u)
                        if len(all_images) >= max_images_total:
                            break

    combined_text = "\n\n".join(all_text_parts).strip()
    return ScrapeResult(
        start_url=start_url,
        visited_urls=visited,
        text=combined_text,
        image_urls=all_images,
    )
