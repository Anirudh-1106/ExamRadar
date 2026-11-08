"""SSC's site is a JavaScript application. We render its public pages in a headless browser exactly as a
visitor would, at low frequency. No login, no CAPTCHA handling, no calls to internal APIs."""

from ..base import Adapter, Item, Listing, classify_text, generic_anchor_items
from ..http import FetchError, FetchResult, PoliteClient, SourceBlocked, looks_like_challenge


class SSC(Adapter):
    key = "ssc"
    sector = "other"

    def fetch(self, client: PoliteClient, url: str, etag: str | None = None, last_modified: str | None = None) -> FetchResult:
        if not client.allowed(url):
            raise FetchError(f"robots.txt disallows {url}")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise FetchError("Playwright is not installed; install the 'browser' extra to collect SSC") from e
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page(user_agent=client.user_agent)
                resp = page.goto(url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(2500)
                html = page.content().encode("utf-8")
                status = resp.status if resp else 0
            finally:
                browser.close()
        if looks_like_challenge(status, html):
            raise SourceBlocked(f"challenge page at {url}")
        return FetchResult(url, url, status, html, "text/html")

    def parse_listing(self, listing: Listing, body: bytes, base_url: str) -> list[Item]:
        items = [i for i in generic_anchor_items(body, base_url, self.content_hosts()) if i.doc_urls]
        for i in items:
            i.kind = classify_text(i.title)
        return items
