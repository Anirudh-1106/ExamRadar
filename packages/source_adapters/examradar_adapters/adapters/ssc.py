"""SSC's site is a JavaScript application. We render its public pages in a headless browser exactly as a
visitor would, at low frequency. No login, no CAPTCHA handling, no calls to internal APIs.

The notice board shows each notice as a dated card whose PDF opens through a click handler, so items link to the
official homepage; dates inside the PDFs are entered or confirmed by an admin until a stable document URL exists."""

import hashlib
import re
from datetime import datetime

from ..base import (
    Adapter,
    CycleHint,
    Item,
    Listing,
    classify_text,
    clean,
    generic_anchor_items,
    slugify,
    soup_of,
)
from ..http import FetchResult, PoliteClient, render_page

MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def exam_hint(title: str) -> CycleHint | None:
    m = re.search(r"((?:Combined|Selection|Junior|Stenographer|Constable|Multi|Sub-Inspector|Central|Delhi|GD|CHSL|CGL|MTS)[A-Za-z ().,&/-]{3,120}?(?:Examination|Exam|Posts?))\s*[,-]?\s*(?:Phase-?[IVX]+/)?(20\d{2})",
                  title, re.I)
    if not m:
        return None
    name = clean(m.group(1))
    return CycleHint(exam_slug=f"ssc-{slugify(name)}", exam_name=name, title=f"{name}, {m.group(2)}", sector="other", year=int(m.group(2)))


class SSC(Adapter):
    key = "ssc"
    sector = "other"

    def fetch(self, client: PoliteClient, url: str, etag: str | None = None, last_modified: str | None = None) -> FetchResult:
        return render_page(client, url)

    def parse_listing(self, listing: Listing, body: bytes, base_url: str) -> list[Item]:
        soup = soup_of(body)
        items: list[Item] = []
        for card in soup.select(".innerCard"):
            box = card.select_one(".dateBox")
            text = card.select_one(".rightSection .text, .rightSection p")
            if not box or not text:
                continue
            parts = [clean(x.get_text()) for x in box.select(".year, .date")]
            title = clean(text.get_text(" "))
            published = None
            try:
                mon, day, year = parts[0][:3].lower(), int(parts[1]), int(parts[2])
                published = datetime(year, MONTHS[mon], day)
            except (IndexError, KeyError, ValueError):
                pass
            if len(title) < 10:
                continue
            key = "ssc-notice:" + hashlib.sha256(f"{published}|{title}".encode()).hexdigest()[:24]
            items.append(Item(key=key, title=title, url=listing.url, kind=classify_text(title), published_hint=published,
                              cycle=exam_hint(title), data={"fetch": False}))
        for i in generic_anchor_items(body, base_url, self.content_hosts()):
            if i.doc_urls:
                i.kind = classify_text(i.title)
                items.append(i)
        return items
