import re
from urllib.parse import unquote, urlparse

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


def exam_hint(name: str) -> CycleHint | None:
    name = clean(name)
    ym = re.search(r"(20\d{2})\s*$", name)
    if not ym or "examination" not in name.lower():
        return None
    year = int(ym.group(1))
    family = re.sub(r"\((?:Preliminary|Main|Prelims)\)\s*", "", name, flags=re.I)
    family = clean(re.sub(r",?\s*20\d{2}\s*$", "", family))
    return CycleHint(exam_slug=f"upsc-{slugify(family)}", exam_name=family, title=f"{family}, {year}",
                     sector="civil_services", year=year)


class UPSC(Adapter):
    key = "upsc"
    sector = "civil_services"

    def parse_listing(self, listing: Listing, body: bytes, base_url: str) -> list[Item]:
        path = urlparse(listing.url).path
        soup = soup_of(body)
        if path.startswith("/whats-new"):
            items = []
            for a in soup.select(".views-field-field-exam-name a[href]"):
                title = clean(a.get_text())
                url = normalise_url(a["href"], base_url)
                exam_part = title.split(":", 1)[-1]
                items.append(Item(key=url, title=title, url=url, kind=classify_text(title), follow=[url],
                                  cycle=exam_hint(exam_part)))
            return items
        if path.startswith(("/examinations/active-exams", "/examinations/forthcoming-exams")):
            items = []
            for a in soup.select(".views-field-field-exam-name a[href]"):
                title = clean(a.get_text())
                url = normalise_url(a["href"], base_url)
                items.append(Item(key=url, title=title, url=url, kind="notification", follow=[url], cycle=exam_hint(title)))
            return items
        if path.startswith("/examinations/exam-calendar"):
            items = []
            for a in soup.find_all("a", href=True):
                t = clean(a.find_parent("tr").get_text(" ")) if a.find_parent("tr") else clean(a.get_text())
                if a["href"].lower().endswith(".pdf") and "calendar" in t.lower():
                    url = normalise_url(a["href"], base_url)
                    items.append(Item(key=url, title=t, url=url, kind="calendar", doc_urls=[url]))
            return items
        return [i for i in generic_anchor_items(body, base_url, self.content_hosts()) if i.doc_urls]

    def parse_detail(self, url: str, body: bytes) -> list[Item]:
        """Exam and what's-new pages list PDFs (notice, result, answer key)."""
        soup = soup_of(body)
        page_title = clean(unquote(urlparse(url).path.rsplit("/", 2)[-2 if "/whats-new/" in url else -1]))
        hint = exam_hint(page_title)
        out = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.lower().split("?")[0].endswith(".pdf"):
                continue
            row = a.find_parent(["li", "tr", "p"])
            label = clean(row.get_text(" ")) if row else clean(a.get_text())
            full = normalise_url(href, url)
            if urlparse(full).netloc not in self.content_hosts():
                continue
            kind = "notification" if re.match(r"notice\b", label, re.I) else classify_text(label + " " + page_title)
            out.append(Item(key=full, title=f"{page_title}: {label}"[:500], url=full, kind=kind, doc_urls=[full], cycle=hint))
        return out

    def extract(self, item: Item, doc) -> list[Fact]:
        from examradar_extraction.rules import generic_facts

        if item.kind == "calendar":
            return calendar_facts(doc)
        if item.kind == "notification":
            return generic_facts(doc)
        from examradar_extraction.rules import event_facts

        return event_facts(doc)


def calendar_facts(doc) -> list[Fact]:
    """UPSC annual calendar rows: name, notification date, last date, commencement date. All tentative."""
    from examradar_extraction.dates import find_dates
    from examradar_extraction.pdf import flat

    facts = []
    for pno, page in enumerate(doc.pages, start=1):
        text = flat(page)
        # Rows are numbered 1., 2., 3. ... Split on that sequence so rows without dates do not swallow the next row.
        starts, pos, n = [], 0, 1
        while True:
            m = re.compile(rf"(?<![\d.]){n}\.\s+(?=[A-Z])").search(text, pos)
            if not m:
                break
            starts.append(m.start())
            pos, n = m.end(), n + 1
        for i, st in enumerate(starts):
            seg = text[st: starts[i + 1] if i + 1 < len(starts) else len(text)]
            seg = re.split(r"\s+Note\s*:", seg)[0].strip()
            ds = find_dates(seg)
            if not ds:
                continue
            name = clean(re.sub(r"^\d{1,2}\.\s+", "", seg[: ds[0].start]))
            if not name or name.lower().startswith("reserved"):
                continue
            exam_d = ds[-1] if len(ds) in (1, 3) else None
            if exam_d is None:
                continue
            hint = exam_hint(name if re.search(r"20\d{2}$", name) else f"{name}, {exam_d.value.year}")
            if not hint:
                hint = CycleHint(exam_slug=f"upsc-{slugify(name)}", exam_name=name,
                                 title=name if re.search(r"20\d{2}", name) else f"{name}, {exam_d.value.year}",
                                 sector="civil_services", year=exam_d.value.year)
            stage = "Main" if re.search(r"\(main\)", name, re.I) else ("Preliminary" if re.search(r"\(prelim", name, re.I) else None)
            quote = seg[: ds[-1].end]
            pairs = list(zip(ds, ("notification", "application_end", "exam"), strict=True)) if len(ds) == 3 else [(exam_d, "exam")]
            for d, et in pairs:
                facts.append(Fact("event", {"event_type": et, "date": d.value.isoformat(), "precision": "day",
                                            "certainty": "tentative", "cycle": hint.__dict__,
                                            "stage": stage if et == "exam" else None}, quote, pno, 0.88))
    return facts
