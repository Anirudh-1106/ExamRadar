"""RBI: the recruitment site serves an image CAPTCHA, so it is never fetched. We read RBI's own published RSS
feeds (offered for subscription) for recruitment-related items, and admins enter the rest manually."""

import re
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from ..base import Adapter, Item, Listing, classify_text, clean

KEYWORDS = re.compile(r"recruit|services board|grade ['‘]?b['’]?|assistant|officer|vacanc|examination|rbisb|apprentice|attendant", re.I)


def parse_rss(body: bytes) -> list[dict]:
    soup = BeautifulSoup(body, "xml")
    out = []
    for it in soup.find_all("item"):
        title = clean(it.find("title").get_text() if it.find("title") else "")
        link_tag = it.find("link")
        link = clean(link_tag.get_text()) if link_tag else ""
        if not link and it.find("guid"):
            link = clean(it.find("guid").get_text())
        pub = it.find("pubDate") or it.find("pubdate")
        when = None
        if pub:
            try:
                when = parsedate_to_datetime(clean(pub.get_text())).replace(tzinfo=None)
            except (TypeError, ValueError):
                when = None
        src = it.find("source")
        out.append({"title": title, "url": link, "published": when, "publisher": clean(src.get_text()) if src else None,
                    "guid": clean(it.find("guid").get_text()) if it.find("guid") else link})
    return out


class RBI(Adapter):
    key = "rbi"
    sector = "banking"

    def parse_listing(self, listing: Listing, body: bytes, base_url: str) -> list[Item]:
        items = []
        for e in parse_rss(body):
            if not e["url"] or not KEYWORDS.search(e["title"]):
                continue
            items.append(Item(key=e["guid"] or e["url"], title=e["title"], url=e["url"], kind=classify_text(e["title"]),
                              published_hint=e["published"], doc_urls=[e["url"]]))
        return items
