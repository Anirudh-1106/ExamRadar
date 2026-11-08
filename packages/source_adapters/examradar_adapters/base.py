"""Adapter contract. Each official source implements discover, fetch, parse_listing, classify, and extract.

Adapters are pure with respect to the database: they turn bytes into Items and Facts. The worker pipeline
owns storage, validation, and publication, so a layout change on one site cannot affect another.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .http import FetchResult, PoliteClient
from .normalise import clean, normalise_url


@dataclass
class Fact:
    field: str  # event | post | vacancies | fee | age_rule | link | qualification | notification_number | photo_spec
    value: dict[str, Any]
    quote: str
    page: int | None = None
    confidence: float = 0.9
    method: str = "rule"


@dataclass
class CycleHint:
    exam_slug: str
    exam_name: str
    title: str
    sector: str = "other"
    year: int | None = None
    notification_number: str | None = None
    category_numbers: list[str] = field(default_factory=list)


@dataclass
class Item:
    key: str
    title: str
    url: str | None
    kind: str = "notice"
    doc_urls: list[str] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)  # evidence is the listing page itself
    cycle: CycleHint | None = None
    published_hint: datetime | None = None
    follow: list[str] = field(default_factory=list)  # detail pages to fetch and parse with parse_detail
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Listing:
    url: str
    kind: str = "listing"  # listing | sitemap | rss | detail
    selector: str | None = None


CLASSIFY_RULES: list[tuple[str, str]] = [
    (r"postpone|re-?schedul|date change|deferred|മാറ്റി", "postponement"),
    (r"cancel", "cancellation"),
    (r"corrigendum|addendum|extension|extended|revised", "corrigendum"),
    (r"answer ?key|उत्तर कुंजी", "answer_key"),
    (r"admit card|hall ticket|admission ticket|call letter|e-call|प्रवेश पत्र", "admit_card"),
    (r"city intimation|exam city", "exam_city"),
    (r"ranked list|rank list", "ranked_list"),
    (r"short ?list|probability list|eligibility list", "short_list"),
    (r"result|select(ion)? list|marks|merit list|cut-?off|परिणाम|चयन सूची", "result"),
    (r"interview", "interview"),
    (r"(document|certificate) verification|\bdv\b|\botv\b", "document_verification"),
    (r"objection", "objection"),
    (r"programme|schedule|calendar|time ?table", "schedule"),
    (r"notification|advertisement|recruitment|applications? (are )?invited|vacanc|\bcen\b|apply online|registration|विज्ञापन|भर्ती अधिसूचना",
     "notification"),
]


def classify_text(text: str) -> str:
    t = text.lower()
    for pat, kind in CLASSIFY_RULES:
        if re.search(pat, t):
            return kind
    return "notice"


def slugify(s: str, maxlen: int = 120) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:maxlen].rstrip("-")


class Adapter:
    key: str = "base"
    org_key: str = ""
    sector: str = "other"

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.org_key = cfg.get("key", self.org_key)

    # 1. which listing pages to check now
    def discover(self) -> list[Listing]:
        out = []
        for entry in self.cfg.get("listings", []):
            if isinstance(entry, str):
                kind = "sitemap" if entry.endswith(".xml") and "sitemap" in entry else "listing"
                out.append(Listing(entry, kind))
            else:
                out.append(Listing(entry["url"], entry.get("kind", "listing"), entry.get("selector")))
        return out

    # 2. fetch through the polite client only
    def fetch(self, client: PoliteClient, url: str, etag: str | None = None,
              last_modified: str | None = None) -> FetchResult:
        return client.get(url, etag=etag, last_modified=last_modified)

    # 3. turn a listing page into items
    def parse_listing(self, listing: Listing, body: bytes, base_url: str) -> list[Item]:
        return generic_anchor_items(body, base_url, self.content_hosts())

    def parse_detail(self, url: str, body: bytes) -> list[Item]:
        return []

    # 4. classify
    def classify(self, item: Item) -> str:
        return item.kind if item.kind != "notice" else classify_text(item.title)

    # 5. extract facts from a document's text (rules only; the pipeline adds LLM for the remainder)
    def extract(self, item: Item, doc: Any) -> list[Fact]:
        from examradar_extraction.rules import generic_facts

        return generic_facts(doc)

    def cycle_hint(self, item: Item) -> CycleHint | None:
        return item.cycle

    def cycle_for_category(self, cat: str, post: str | None, department: str | None) -> CycleHint | None:
        """Sources with category numbers build a cycle for a number seen before its notification."""
        return None

    def doc_options(self, item: Item) -> dict[str, Any]:
        return {"tables": False}

    # helpers
    def content_hosts(self) -> set[str]:
        return {d["host"] for d in self.cfg.get("domains", []) if d.get("purpose") == "content"}


def soup_of(body: bytes | str) -> BeautifulSoup:
    return BeautifulSoup(body, "lxml")


def generic_anchor_items(body: bytes, base_url: str, hosts: set[str], min_len: int = 12) -> list[Item]:
    """Fallback: every document-like link on an official host becomes an item."""
    soup = soup_of(body)
    items: dict[str, Item] = {}
    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        if href.startswith(("javascript:", "mailto:", "#", "tel:")):
            continue
        url = normalise_url(href, base_url)
        host = urlparse(url).netloc
        title = clean(a.get_text(" "))
        if len(title) < min_len:
            parent = a.find_parent(["li", "p", "tr", "div"])
            title = clean(parent.get_text(" ")) if parent is not None else title
        if host not in hosts or len(title) < min_len or len(title) > 600:
            continue
        is_doc = url.lower().split("?")[0].endswith((".pdf", ".doc", ".docx"))
        if url not in items:
            items[url] = Item(key=url, title=title, url=url, doc_urls=[url] if is_doc else [])
    return list(items.values())
