"""Validation gates between extraction and publication."""

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from urllib.parse import urlparse

from .malayalam import normalise_for_match

AUTO_PUBLISH_CONFIDENCE = 0.85


@dataclass
class QuoteMatch:
    ok: bool
    page: int | None = None
    start: int | None = None
    end: int | None = None


def _compact(s: str) -> str:
    return re.sub(r"\s+", "", normalise_for_match(s))


def verify_quote(quote: str, pages: list[str]) -> QuoteMatch:
    """The quote must appear in the stored document text. Whitespace is ignored; every other character must match.

    Table evidence is written as 'cell | cell'; each cell must then appear on the same page.
    """
    if not quote or not quote.strip():
        return QuoteMatch(False)
    parts = [p for p in (x.strip() for x in quote.split(" | ")) if p] if " | " in quote else [quote]
    offset = 0
    for i, page in enumerate(pages, start=1):
        cp = _compact(page)
        if all(_compact(p) in cp for p in parts):
            first = cp.find(_compact(parts[0]))
            return QuoteMatch(True, i, offset + first, offset + first + len(_compact(parts[0])))
        offset += len(cp)
    return QuoteMatch(False)


@dataclass
class DateCheck:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def check_event_date(event_type: str, d: date, today: date, published_on: date | None = None) -> DateCheck:
    c = DateCheck()
    if d < today - timedelta(days=3 * 365) or d > today + timedelta(days=3 * 365):
        c.errors.append(f"improbable date {d.isoformat()} for {event_type}")
    if published_on and event_type in {"application_end", "exam", "confirmation_deadline"} and d < published_on:
        c.errors.append(f"{event_type} {d.isoformat()} is before the document date {published_on.isoformat()}")
    if d.weekday() == 6 and event_type == "application_end":
        c.warnings.append("deadline falls on a Sunday")
    return c


ORDER_RULES = [
    ("notification", "application_end"),
    ("application_start", "application_end"),
    ("application_end", "exam"),
    ("confirmation_deadline", "exam"),
    ("admit_card", "exam"),
    ("exam", "answer_key"),
    ("exam", "result"),
]


def check_ordering(events: dict[str, list[date]]) -> list[str]:
    """events maps event_type to dates for one exam cycle (and stage). Returns ordering violations."""
    errs = []
    for a, b in ORDER_RULES:
        if events.get(a) and events.get(b) and min(events[a]) > max(events[b]):
            errs.append(f"{a} ({min(events[a]).isoformat()}) is after {b} ({max(events[b]).isoformat()})")
    return errs


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower().rstrip(".")


def link_allowed(url: str, domains: list[dict], purposes: tuple[str, ...] = ("apply", "content", "portal")) -> bool:
    """Exact hostname match, scoped to one organisation's allowlist. Subdomains are not trusted implicitly."""
    p = urlparse(url)
    if p.scheme not in ("https", "http"):
        return False
    host = host_of(url)
    path = p.path or "/"
    for d in domains:
        if d.get("purpose") in purposes and d["host"].lower() == host and path.startswith(d.get("path_prefix") or "/"):
            return True
    return False
