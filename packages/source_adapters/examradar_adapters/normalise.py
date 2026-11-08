"""Reduce false change detection: strip volatile markup, then hash what remains."""

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

VOLATILE_PARAMS = {"t", "ts", "timestamp", "_", "v", "ver", "sid", "sessionid", "jsessionid", "phpsessid", "cache"}


def normalise_url(url: str, base: str | None = None) -> str:
    if base:
        url = urljoin(base, url)
    p = urlparse(url.strip())
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in VOLATILE_PARAMS]
    path = re.sub(r"/{2,}", "/", p.path) or "/"
    return urlunparse((p.scheme.lower() or "https", p.netloc.lower(), path, "", urlencode(q), ""))


def main_text(html: str | bytes, selector: str | None = None) -> str:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript", "iframe", "svg", "form", "input"]):
        t.decompose()
    root = soup.select_one(selector) if selector else None
    if root is None:
        for t in soup(["nav", "header", "footer"]):
            t.decompose()
        root = soup.body or soup
    text = root.get_text("\n", strip=True)
    text = re.sub(r"(visitor|hit)s?\s*(count(er)?)?\s*[:\-]?\s*\d[\d,]*", "", text, flags=re.I)
    text = re.sub(r"last updated\s*(on)?\s*[:\-]?.{0,40}", "", text, flags=re.I)
    return re.sub(r"[ \t]+", " ", text).strip()


def text_hash(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode()).hexdigest()


def clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", s or "").strip()
