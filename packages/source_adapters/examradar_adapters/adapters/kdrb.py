import re
from urllib.parse import urlparse

from ..base import (
    Adapter,
    CycleHint,
    Fact,
    Item,
    Listing,
    classify_text,
    clean,
    generic_anchor_items,
    slugify,
    soup_of,
)
from ..normalise import normalise_url

RE_CAT = re.compile(r"CAT(?:EGORY)?\.?\s*NO\.?\s*:?\s*(\d{1,3})\s*/\s*(\d{4})", re.I)
RE_ON = re.compile(r"\bON\s+(\d{2}\.\d{2}\.\d{4})", re.I)


class KDRB(Adapter):
    key = "kdrb"
    sector = "devaswom"

    def parse_listing(self, listing: Listing, body: bytes, base_url: str) -> list[Item]:
        from examradar_extraction.dates import parse_date

        if urlparse(listing.url).netloc.startswith("recruitment."):
            return [i for i in generic_anchor_items(body, base_url, {urlparse(listing.url).netloc}) if i.doc_urls]
        items = []
        for art in soup_of(body).find_all("article"):
            a = art.select_one(".entry-title a[href]")
            if not a:
                continue
            title, href = clean(a.get_text(" ")), normalise_url(a["href"], base_url)
            cats = [f"{int(n):03d}/{y}" for n, y in RE_CAT.findall(title)]
            kind = classify_text(title)
            facts = []
            on = RE_ON.search(title)
            if on and kind in ("document_verification", "interview", "exam", "schedule") and (d := parse_date(on.group(1))):
                et = kind if kind in ("document_verification", "interview") else "exam"
                facts.append(Fact("event", {"event_type": et, "date": d.value.isoformat(), "precision": "day", "certainty": "official",
                                            "category_numbers": cats}, title, None, 0.8))
            hint = self.cycle_for_category(cats[0], None, None) if len(cats) == 1 else None
            items.append(Item(key=href, title=title, url=href, kind=kind, facts=facts, follow=[href], cycle=hint,
                              data={"category_numbers": cats}))
        return items

    def parse_detail(self, url: str, body: bytes) -> list[Item]:
        soup = soup_of(body)
        title = clean((soup.select_one(".entry-title") or soup.title or soup).get_text(" "))[:400]
        cats = [f"{int(n):03d}/{y}" for n, y in RE_CAT.findall(title)]
        out = []
        for a in soup.select(".entry-content a[href], article a[href]"):
            href = normalise_url(a["href"], url)
            if href.lower().endswith(".pdf") and urlparse(href).netloc in self.content_hosts():
                out.append(Item(key=href, title=f"{title}: {clean(a.get_text(' '))}"[:500], url=href, kind=classify_text(title),
                                doc_urls=[href], cycle=self.cycle_for_category(cats[0], None, None) if len(cats) == 1 else None))
        return out

    def cycle_for_category(self, cat: str, post: str | None, department: str | None) -> CycleHint:
        name = clean(post) or f"KDRB Category {cat}"
        return CycleHint(exam_slug=f"kdrb-{slugify(name)}" if post else f"kdrb-cat-{cat.replace('/', '-')}", exam_name=name,
                         title=f"{name} (Cat. No. {cat})", sector="devaswom", year=int(cat[-4:]),
                         notification_number=f"Cat. No. {cat}", category_numbers=[cat])
