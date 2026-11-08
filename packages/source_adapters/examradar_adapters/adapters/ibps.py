import re
from urllib.parse import urlparse

from ..base import Adapter, CycleHint, Fact, Item, Listing, classify_text, clean, slugify, soup_of
from ..normalise import normalise_url

RE_REG_FROM = re.compile(r"registration\s+(?:from|starts?)\s+(\d{1,2}-[A-Za-z]{3}-\d{4})", re.I)
RE_CRP = re.compile(r"CRP[\s-]*((?:RRB[\s-]*)?(?:PO/MTs?|PO/MT|SPL|CSA|Clerks?|SO|PO|RRBs?)?)[\s-]*([XVI]+)", re.I)


def hint_for(title: str) -> CycleHint | None:
    m = RE_CRP.search(title)
    if m:
        kind = clean(m.group(1)).upper().replace("MTS", "MT") or "CRP"
        return CycleHint(exam_slug=f"ibps-crp-{slugify(kind)}", exam_name=f"IBPS CRP {kind}",
                         title=f"IBPS CRP {kind}-{m.group(2).upper()}", sector="banking", notification_number=f"CRP {kind}-{m.group(2).upper()}")
    rm = re.match(r"(.{3,80}?)\s+Recruitment of\s+(.{3,120}?)(?:\s+Registration|\s*$)", title, re.I)
    if rm:
        name = f"{clean(rm.group(1))} {clean(rm.group(2))}"
        return CycleHint(exam_slug=f"ibps-{slugify(name)}", exam_name=name, title=name, sector="banking")
    return None


class IBPS(Adapter):
    key = "ibps"
    sector = "banking"

    def parse_listing(self, listing: Listing, body: bytes, base_url: str) -> list[Item]:
        from examradar_extraction.dates import parse_date

        skip = tuple(self.cfg.get("skip_title_prefixes", []))
        hosts = self.content_hosts() | {d["host"] for d in self.cfg.get("domains", [])}
        items: dict[str, Item] = {}
        for a in soup_of(body).find_all("a", href=True):
            title = clean(a.get_text(" "))
            href = normalise_url(a["href"], base_url)
            if urlparse(href).netloc not in hosts or len(title) < 15 or title.upper().startswith(skip):
                continue
            is_pdf = href.lower().split("?")[0].endswith(".pdf")
            on_reg = urlparse(href).netloc == "ibpsreg.ibps.in"
            if not (is_pdf or on_reg):
                continue
            facts = []
            m = RE_REG_FROM.search(title)
            if m and (d := parse_date(m.group(1))):
                facts.append(Fact("event", {"event_type": "application_start", "date": d.value.isoformat(), "precision": "day",
                                            "certainty": "official"}, m.group(0), None, 0.9))
            kind = classify_text(title)
            if on_reg:
                facts.append(Fact("link", {"kind": "apply" if kind == "notification" else kind, "url": href, "label": title},
                                  title, None, 0.9))
            item = items.get(href) or Item(key=href, title=title, url=href, kind=kind, doc_urls=[href] if is_pdf else [],
                                           facts=facts, cycle=hint_for(title))
            items[href] = item
        return list(items.values())

    def extract(self, item: Item, doc) -> list[Fact]:
        from examradar_extraction.rules import event_facts, generic_facts

        return generic_facts(doc) if item.kind == "notification" else event_facts(doc)
