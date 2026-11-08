"""News publisher RSS feeds. These are signals, not sources of exam data.

A matching headline is stored as a NewsItem (shown in the app as an unverified mention with a link to the
publisher), creates a missed-notice candidate for admins when no official item matches, and triggers an
immediate re-check of the organisation's official sources.
"""

import re
from dataclasses import dataclass
from datetime import datetime

from .adapters.rbi import parse_rss

ORG_PATTERNS: dict[str, str] = {
    "kerala_psc": r"kerala\s*psc|\bkpsc\b|public service commission.*kerala|പി\.?\s?എസ്\.?\s?സി",
    "kdrb": r"devaswom recruitment|\bkdrb\b|ദേവസ്വം",
    "upsc": r"\bupsc\b|union public service|civil services exam|\bcse\b|\bnda\b|\bcds\b",
    "ssc": r"\bssc\b|staff selection commission|\bcgl\b|\bchsl\b|\bmts\b|\bgd constable\b",
    "ibps": r"\bibps\b",
    "sbi": r"\bsbi\b.*(po|clerk|recruit|junior associate|sco|vacanc)|state bank of india.*(recruit|exam)",
    "rbi": r"\brbi\b.*(recruit|grade b|assistant|exam|vacanc|officer)|reserve bank.*(recruit|exam)",
    "rrb": r"\brrb\b|railway recruitment|\bntpc\b|\balp\b|group d",
    "nta": r"ugc[- ]?net|csir[- ]?net|\bnta\b",
}
JOB_WORDS = re.compile(
    r"recruit|notification|vacanc|exam|admit card|hall ticket|answer key|result|apply|application|last date|cut-?off|"
    r"rank list|short ?list|syllabus|calendar|postpon|interview|merit|വിജ്ഞാപനം|പരീക്ഷ|റാങ്ക്", re.I)


@dataclass
class NewsEntry:
    guid: str
    title: str
    url: str
    publisher: str | None
    published: datetime | None
    organisations: list[str]


def match_orgs(title: str) -> list[str]:
    return [k for k, p in ORG_PATTERNS.items() if re.search(p, title, re.I)]


def parse_feed(body: bytes, default_publisher: str | None = None) -> list[NewsEntry]:
    out = []
    for e in parse_rss(body):
        if not e["title"] or not e["url"] or not JOB_WORDS.search(e["title"]):
            continue
        orgs = match_orgs(e["title"])
        if not orgs:
            continue
        out.append(NewsEntry(e["guid"] or e["url"], e["title"], e["url"], e["publisher"] or default_publisher,
                             e["published"], orgs))
    return out
