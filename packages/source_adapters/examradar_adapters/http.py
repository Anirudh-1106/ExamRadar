"""The only way adapters may touch the network.

Enforces robots.txt, per-host minimum delay with jitter, conditional requests, size and time limits,
retry with exponential backoff, and detection of bot-challenge pages. A challenge page is never retried
or worked around: it raises SourceBlocked so the source is marked blocked and an admin is told.
"""

import random
import ssl
import threading
import time
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import certifi
import httpx
from examradar_core.settings import get_settings


class FetchError(Exception):
    pass


class SourceBlocked(FetchError):
    """The site served a CAPTCHA, firewall rejection, or similar. Do not retry automatically."""


class RobotsDisallowed(FetchError):
    pass


CHALLENGE_MARKERS = (
    "What code is in the image",
    "The requested URL was rejected",
    "Request Rejected",
    "/TSPD/",
    "cf-challenge",
    "Attention Required! | Cloudflare",
    "Please enable JavaScript to view the page content. Your support ID",
    "You are not authorized to view this page",
)


def looks_like_challenge(status: int, body: bytes) -> bool:
    if status in (403, 418, 429):
        return True
    head = body[:20000].decode("utf-8", "ignore")
    return any(m in head for m in CHALLENGE_MARKERS)


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int
    content: bytes
    content_type: str
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False
    headers: dict[str, str] = field(default_factory=dict)


def tls_context() -> ssl.SSLContext:
    """Normal certificate verification, plus intermediate certificates that some official sites fail to send.

    Verification is never turned off. config/extra-ca.pem holds only intermediates downloaded from the issuing
    CA's own address (see docs/decisions.md D14); each must chain to a root already in the trust store.
    """
    ctx = ssl.create_default_context(cafile=certifi.where())
    extra = Path(get_settings().crawler_extra_ca_file)
    if extra.exists():
        ctx.load_verify_locations(cafile=str(extra))
    return ctx


class PoliteClient:
    def __init__(self, user_agent: str | None = None, min_delay: float | None = None,
                 transport: httpx.BaseTransport | None = None, respect_robots: bool = True):
        s = get_settings()
        self.user_agent = user_agent or s.crawler_user_agent
        self.min_delay = s.crawler_default_min_delay_seconds if min_delay is None else min_delay
        self.max_bytes = s.crawler_max_bytes
        self.respect_robots = respect_robots
        self._client = httpx.Client(
            headers={"User-Agent": self.user_agent, "Accept-Language": "en-IN,en;q=0.8,ml;q=0.5"},
            timeout=s.crawler_timeout_seconds,
            follow_redirects=True,
            transport=transport,
            verify=tls_context(),
        )
        self._last_hit: dict[str, float] = {}
        self._host_delay: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._lock = threading.Lock()

    def set_host_delay(self, host: str, seconds: float) -> None:
        self._host_delay[host] = seconds

    # -------------------------------------------------------------- robots
    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        if base in self._robots:
            return self._robots[base]
        rp: urllib.robotparser.RobotFileParser | None = urllib.robotparser.RobotFileParser()
        try:
            r = self._client.get(base + "/robots.txt")
            ctype = r.headers.get("content-type", "")
            if r.status_code == 200 and "text/plain" in ctype:
                assert rp is not None
                rp.parse(r.text.splitlines())
            else:
                # No robots.txt (404, or an HTML page served instead) means no restrictions were published.
                rp = None
        except httpx.HTTPError:
            rp = None
        self._robots[base] = rp
        return rp

    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        rp = self._robots_for(url)
        return True if rp is None else rp.can_fetch(self.user_agent, url)

    # -------------------------------------------------------------- pacing
    def _wait_turn(self, host: str) -> None:
        delay = self._host_delay.get(host, self.min_delay)
        with self._lock:
            last = self._last_hit.get(host)
            now = time.monotonic()
            if last is not None:
                wait = delay + random.uniform(0, delay * 0.3) - (now - last)
                if wait > 0:
                    time.sleep(wait)
            self._last_hit[host] = time.monotonic()

    # -------------------------------------------------------------- fetch
    def get(self, url: str, etag: str | None = None, last_modified: str | None = None,
            retries: int = 2) -> FetchResult:
        if not self.allowed(url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")
        host = urlparse(url).netloc
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        attempt = 0
        while True:
            self._wait_turn(host)
            try:
                with self._client.stream("GET", url, headers=headers) as r:
                    chunks, size = [], 0
                    for chunk in r.iter_bytes():
                        size += len(chunk)
                        if size > self.max_bytes:
                            raise FetchError(f"response larger than {self.max_bytes} bytes")
                        chunks.append(chunk)
                    body = b"".join(chunks)
                    status = r.status_code
                    hdrs = {k.lower(): v for k, v in r.headers.items()}
                    final = str(r.url)
            except httpx.HTTPError as e:
                if attempt >= retries:
                    raise FetchError(f"{type(e).__name__}: {e}") from e
                attempt += 1
                time.sleep(min(60, (2 ** attempt) * 2 + random.uniform(0, 2)))
                continue
            if status == 304:
                return FetchResult(url, final, 304, b"", hdrs.get("content-type", ""), etag, last_modified, True, hdrs)
            if looks_like_challenge(status, body):
                raise SourceBlocked(f"challenge or block page (HTTP {status}) at {url}")
            if status >= 500 and attempt < retries:
                attempt += 1
                time.sleep(min(60, (2 ** attempt) * 2 + random.uniform(0, 2)))
                continue
            if status >= 400:
                raise FetchError(f"HTTP {status} for {url}")
            return FetchResult(url, final, status, body, hdrs.get("content-type", ""),
                               hdrs.get("etag"), hdrs.get("last-modified"), False, hdrs)

    def close(self) -> None:
        self._client.close()


def render_page(client: "PoliteClient", url: str, wait_ms: int = 2500) -> FetchResult:
    """Render a public page in headless Chromium, as a visitor's browser would. Used only for JavaScript-only sites.

    Same identity (User-Agent) as the HTTP client, robots.txt is checked first, and challenge pages raise SourceBlocked.
    """
    if not client.allowed(url):
        raise RobotsDisallowed(f"robots.txt disallows {url}")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise FetchError("Playwright is not installed; install the 'browser' extra for JavaScript-only sources") from e
    client._wait_turn(urlparse(url).netloc)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(user_agent=client.user_agent)
            resp = page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(wait_ms)
            html = page.content().encode("utf-8")
            status = resp.status if resp else 0
            final = page.url
        finally:
            browser.close()
    if looks_like_challenge(status, html):
        raise SourceBlocked(f"challenge or block page (HTTP {status}) at {url}")
    if status >= 400:
        raise FetchError(f"HTTP {status} for {url}")
    return FetchResult(url, final, status, html, "text/html")
