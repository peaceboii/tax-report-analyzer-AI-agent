"""
utils/web_scraper.py
────────────────────
BrowserAgent equivalent: fetches URLs and extracts clean article text.
Used by the WebSearchAgent when RAG context is insufficient.
"""

from __future__ import annotations

import re
import time
from typing import Optional
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def google_search_urls(query: str, num: int = 5) -> list[dict]:
    """
    Perform a Google search and return the top result URLs.
    Uses the unofficial Google search endpoint (no API key required).
    Returns a list of {"title": ..., "url": ...} dicts.
    """
    search_url = f"https://www.google.com/search?q={quote_plus(query)}&num={num * 2}"
    try:
        resp = requests.get(search_url, headers=_HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for a in soup.select("a[href]"):
            href = a["href"]
            # Google wraps links in /url?q=...
            if href.startswith("/url?q="):
                real_url = href[7:].split("&")[0]
                if real_url.startswith("http"):
                    title_el = a.find("h3")
                    title = title_el.get_text(strip=True) if title_el else real_url
                    if not any(r["url"] == real_url for r in results):
                        results.append({"title": title, "url": real_url})
            if len(results) >= num:
                break
        return results
    except Exception as e:
        return [{"title": "Search failed", "url": "", "error": str(e)}]


def scrape_url(url: str, max_chars: int = 3000) -> str:
    """
    Fetch a URL and extract clean article text.
    Returns the cleaned text (truncated to `max_chars`).
    """
    if not url:
        return ""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove boilerplate
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()

        # Get main content
        for candidate in ["article", "main", ".content", "#content", "body"]:
            el = soup.select_one(candidate)
            if el:
                text = el.get_text(separator="\n", strip=True)
                break
        else:
            text = soup.get_text(separator="\n", strip=True)

        # Collapse whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text[:max_chars]
    except Exception as e:
        return f"[Scrape error for {url}: {e}]"


def web_search_and_scrape(
    query: str,
    num_results: int = 4,
    max_chars_per_page: int = 2000,
) -> dict:
    """
    End-to-end: search Google → scrape top results → return aggregated context.

    Returns:
        {
            "context": str,          # concatenated text
            "sources": [{"title": str, "url": str}, ...]
        }
    """
    results = google_search_urls(query, num=num_results)
    if not results:
        return {"context": "", "sources": []}

    context_parts: list[str] = []
    valid_sources: list[dict] = []

    for r in results:
        url = r.get("url", "")
        if not url:
            continue
        text = scrape_url(url, max_chars=max_chars_per_page)
        if text and not text.startswith("[Scrape error"):
            context_parts.append(f"--- Source: {url} ---\n{text}")
            valid_sources.append({"title": r.get("title", url), "url": url})
        time.sleep(0.3)  # polite crawl delay

    return {
        "context": "\n\n".join(context_parts),
        "sources": valid_sources,
    }
