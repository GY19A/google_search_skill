"""
Google Search helper.
Uses googlesearch-python and ddgs as fallback search providers.
Supports multiple search sources and basic fault tolerance.
"""

import time
import random
import shutil
import subprocess
import tempfile
from typing import List, Dict, Any, Optional, Union
from urllib.parse import parse_qs, unquote, urlparse
from bs4 import BeautifulSoup
import requests
from googlesearch import search
from ddgs import DDGS


def get_useragent() -> str:
    """Generate a realistic desktop browser User-Agent."""
    user_agents = [
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
    ]
    return random.choice(user_agents)


def _build_google_headers(lang: str) -> Dict[str, str]:
    """Build browser-like request headers for Google search."""
    return {
        "User-Agent": get_useragent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": f"{lang},en;q=0.9",
        "Referer": "https://www.google.com/",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def _build_google_search_url(query: str, max_results: int, lang: str, gl: str, start: int) -> str:
    """Build a Google search URL with stable query parameters."""
    request = requests.Request(
        "GET",
        "https://www.google.com/search",
        params={
            "q": query,
            "num": max_results + 2,
            "hl": lang,
            "gl": gl,
            "pws": "0",
            "ie": "UTF-8",
            "oe": "UTF-8",
            "udm": "14",
            "gbv": "1",
            "filter": "0",
            "start": start,
            "safe": "active",
        },
    )
    return request.prepare().url or "https://www.google.com/search"


def _render_google_html_with_chrome(url: str, lang: str, user_agent: str) -> str:
    """Render a page with headless Chrome and return the final DOM."""
    chrome_path = (
        shutil.which("google-chrome")
        or shutil.which("google-chrome-stable")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
    )
    if not chrome_path:
        return ""

    with tempfile.TemporaryDirectory(prefix="google-search-") as user_data_dir:
        command = [
            chrome_path,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--hide-scrollbars",
            "--window-size=1440,2400",
            "--virtual-time-budget=8000",
            f"--user-agent={user_agent}",
            f"--lang={lang}",
            f"--user-data-dir={user_data_dir}",
            "--dump-dom",
            url,
        ]

        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception:
            return ""

        html = completed.stdout.strip()
        return html


def _normalize_google_href(href: str) -> str:
    """Extract the final destination URL from a Google redirect link."""
    if not href:
        return ""

    if href.startswith("/url?") or "google.com/url?" in href:
        parsed = urlparse(href)
        query = parse_qs(parsed.query)
        for key in ("q", "url", "u"):
            values = query.get(key)
            if values and values[0]:
                return unquote(values[0])
        return ""

    if href.startswith("/url?q="):
        return unquote(href.split("/url?q=", 1)[1].split("&", 1)[0])

    return unquote(href)


def _extract_text(node) -> str:
    """Return normalized text from a BeautifulSoup node."""
    return node.get_text(" ", strip=True) if node else ""


def _extract_result_from_block(block) -> Dict[str, str] | None:
    """Extract a single Google result from one candidate HTML block."""
    title_node = None
    for selector in ("h3", "span.CVA68e", "span.lV0lJf", "div[role='heading']"):
        title_node = block.select_one(selector)
        if title_node and _extract_text(title_node):
            break

    link_node = title_node.find_parent("a", href=True) if title_node else None
    if not link_node:
        link_node = block.find("a", href=True)

    title = _extract_text(title_node)
    url = _normalize_google_href(link_node.get("href", "")) if link_node else ""

    if not title or not url:
        return None

    snippet = ""
    for selector in ("div.VwiC3b", "div.IsZvec", "span.FrIlee", "div[data-sncf]", "span.aCOpRe"):
        snippet_node = block.select_one(selector)
        snippet = _extract_text(snippet_node)
        if snippet:
            break

    return {
        "title": title,
        "url": url,
        "description": snippet,
        "score": None,
        "raw_content": snippet,
    }


def _collect_google_results(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """Collect search results using multiple candidate Google layouts."""
    results: List[Dict[str, str]] = []
    seen_links: set[str] = set()

    candidate_selectors = (
        "div.g",
        "div.MjjYud",
        "div.ezO2md",
        "div[data-sncf]",
    )

    blocks = []
    for selector in candidate_selectors:
        blocks.extend(soup.select(selector))

    if not blocks:
        for heading in soup.select("h3"):
            container = heading.find_parent("div")
            if container:
                blocks.append(container)

    for block in blocks:
        result = _extract_result_from_block(block)
        if not result:
            continue

        if result["url"] in seen_links:
            continue

        seen_links.add(result["url"])
        results.append(result)

    return results


def google_search_ddgs(
    query: str,
    num_results: int = 10,
    lang: str = "en"
) -> List[Dict[str, str]]:
    """
    Use DDGS (DuckDuckGo) as a Google search fallback.

    Args:
        query: Search query.
        num_results: Number of results to return.
        lang: Language code.

    Returns:
        List[Dict]: Search result list.
    """
    results = []
    try:
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=num_results):
                results.append({
                    "title": item.get("title", "N/A"),
                    "url": item.get("href", ""),
                    "description": item.get("body", ""),
                    "score": None,
                    "raw_content": item.get("body", "")
                })
    except Exception as e:
        print(f"DDGS search error: {str(e)}")

    return results


def google_search_requests(
    query: str,
    max_results: int = 10,
    lang: str = "en",
    gl: str = "us",
    sleep_interval: float = 1.0,
    use_js_rendering: bool = True,
) -> List[Dict[str, str]]:
    """
    Fetch Google search results directly via requests.

    Args:
        query: Search query.
        max_results: Maximum number of results.
        lang: Language code.
        sleep_interval: Delay between requests.

    Returns:
        List[Dict]: Search results with title, url, and description.
    """
    results = []
    start = 0
    fetched_results = 0
    fetched_links: set[str] = set()

    while fetched_results < max_results:
        try:
            search_url = _build_google_search_url(query, max_results, lang, gl, start)
            html = ""

            if use_js_rendering:
                html = _render_google_html_with_chrome(search_url, lang, get_useragent())

            if not html:
                resp = requests.get(
                    url=search_url,
                    headers=_build_google_headers(lang),
                    timeout=15,
                )
                resp.raise_for_status()
                html = resp.text

            soup = BeautifulSoup(html, "html.parser")
            page_results = _collect_google_results(soup)
            new_results = 0

            for result in page_results:
                link = result["url"]
                if link in fetched_links:
                    continue

                fetched_links.add(link)
                results.append(result)
                fetched_results += 1
                new_results += 1

                if fetched_results >= max_results:
                    break

            if new_results == 0:
                break

            start += 10
            time.sleep(sleep_interval)

        except Exception as e:
            print(f"Google search error for '{query}': {str(e)}")
            break

    return results


def google_search_googlesearch(
    query: str,
    num_results: int = 10,
    lang: str = "en",
    sleep_interval: float = 1.0
) -> List[Dict[str, str]]:
    """
    Use the googlesearch-python package for Google search.

    Args:
        query: Search query.
        num_results: Number of results to return.
        lang: Language code.
        sleep_interval: Delay between requests.

    Returns:
        List[Dict]: Search result list.
    """
    results = []
    count = 0

    try:
        for url in search(
            query,
            num_results=num_results,
            lang=lang,
            advanced=True,
            sleep_interval=sleep_interval
        ):
            if url.url:
                results.append({
                    "title": url.title or "N/A",
                    "url": url.url,
                    "description": url.description or "",
                    "score": None,
                    "raw_content": url.description or ""
                })
                count += 1
                if count >= num_results:
                    break

    except Exception as e:
        print(f"Google search error: {str(e)}")

    return results


def google_search(
    query: str,
    num_results: int = 10,
    lang: str = "en",
    gl: str = "us",
    use_js_rendering: bool = True
) -> List[Dict[str, Any]]:
    """
    Main Google search entry point.
    Selects the best available search method automatically.

    Args:
        query: Search query.
        num_results: Number of results to return, default 10.
        lang: Language code, default en.

    Returns:
        List[Dict]: Dictionaries containing title, url, and description.
    """
    # Prefer requests first for the most direct parsing path.
    results = google_search_requests(
        query,
        max_results=num_results,
        lang=lang,
        gl=gl,
        use_js_rendering=use_js_rendering,
    )

    if not results:
        # Fall back to DDGS if requests fails.
        results = google_search_ddgs(query, num_results=num_results, lang=lang)

    if not results:
        # Fall back to googlesearch-python if DDGS also fails.
        results = google_search_googlesearch(query, num_results=num_results, lang=lang)

    return results


async def google_search_async(
    search_queries: Union[str, List[str]],
    max_results: int = 5,
    lang: str = "en",
    gl: str = "us",
    use_js_rendering: bool = True
) -> List[Dict[str, Any]]:
    """
    Async Google search helper.

    Args:
        search_queries: One query or a list of queries.
        max_results: Maximum results per query.
        lang: Language code.

    Returns:
        List[Dict]: Search result list.
    """
    if isinstance(search_queries, str):
        search_queries = [search_queries]

    results = []
    for query in search_queries:
        query_results = google_search(
            query,
            num_results=max_results,
            lang=lang,
            gl=gl,
            use_js_rendering=use_js_rendering,
        )
        results.extend(query_results)

    return results


if __name__ == "__main__":
    import sys

    # Accept search queries from the command line.
    # Usage: python google_search.py "query1" "query2" ...
    # Example: python google_search.py "Genomaker AI" "genome foundation model"
    SEARCH_QUERIES = sys.argv[1:] if len(sys.argv) > 1 else ["Google search test"]

    # Run the main search helper for each query.
    all_results = []
    for query in SEARCH_QUERIES:
        print(f"\nSearch: {query}")
        results = google_search(query, num_results=5)
        all_results.extend(results)

    print(f"\nTotal results: {len(all_results)}")
    for i, r in enumerate(all_results, 1):
        print(f"  {i}. {r['title']}")
        print(f"     {r['url']}")