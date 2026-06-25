import asyncio
import httpx
from urllib.parse import urlparse
from utils.logger import get_logger

log = get_logger("scraper")

# Realistic browser UA to avoid bot detection
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def extract_domain(url: str) -> str:
    """Extract clean domain (no www, no path) from a URL."""
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        return domain.replace("www.", "").strip("/").lower().split(":")[0]
    except Exception:
        return ""


async def search_google_maps(query: str, location: str, api_key: str) -> list:
    """Search Google Places API for local businesses."""
    if not api_key or api_key == "placeholder":
        log.warning("Google Maps API key not configured")
        return []

    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.get(
                "https://maps.googleapis.com/maps/api/place/textsearch/json",
                params={
                    "query": f"{query} in {location}",
                    "key": api_key,
                    "type": "establishment",
                },
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            leads = [
                {
                    "company_name": r.get("name", ""),
                    "location": r.get("formatted_address", ""),
                    "google_rating": r.get("rating"),
                    "place_id": r.get("place_id"),
                    "source": "google_maps",
                    "domain": "",  # Enriched later
                }
                for r in results
            ]
            log.info(f"Google Maps: {len(leads)} results for '{query}' in {location}")
            return leads
        except Exception as e:
            log.warning(f"Google Maps search failed: {e}")
            return []


async def scrape_company_context(domain: str) -> str:
    """
    Scrape company About page and return raw text (max 3000 chars).
    Tries /about, /about-us, /company, then homepage.
    Uses httpx (no JS). For JS-heavy sites, see scrape_company_context_playwright.
    """
    urls_to_try = [
        f"https://{domain}/about",
        f"https://{domain}/about-us",
        f"https://{domain}/company",
        f"https://{domain}",
    ]

    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for url in urls_to_try:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200 and len(resp.text) > 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                        tag.decompose()
                    text = soup.get_text(separator=" ", strip=True)
                    # Collapse whitespace
                    import re
                    text = re.sub(r"\s+", " ", text).strip()
                    if len(text) > 100:
                        log.debug(f"Scraped {domain} ({len(text)} chars) from {url}")
                        return text[:3000]
            except Exception:
                continue

    log.debug(f"Could not scrape {domain}")
    return ""


async def scrape_company_context_playwright(domain: str) -> str:
    """
    Playwright-based scraper for JS-heavy sites.
    Only use this when httpx scraper returns empty results.
    Requires: playwright install chromium
    """
    try:
        from playwright.async_api import async_playwright
        urls_to_try = [
            f"https://{domain}/about",
            f"https://{domain}/about-us",
            f"https://{domain}",
        ]
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(user_agent=USER_AGENT)
            text = ""
            for url in urls_to_try:
                try:
                    await page.goto(url, timeout=12000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(1000)  # Wait for JS
                    text = await page.inner_text("body")
                    if len(text) > 200:
                        break
                except Exception:
                    continue
            await browser.close()
        return text[:3000] if text else ""
    except Exception as e:
        log.warning(f"Playwright scrape failed for {domain}: {e}")
        return ""
