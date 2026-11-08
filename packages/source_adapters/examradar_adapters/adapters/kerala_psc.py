import re
from urllib.parse import urlparse

from ..base import Adapter, CycleHint, Fact, Item, Listing, clean, generic_anchor_items, slugify, soup_of
from ..normalise import normalise_url

LATEST_KIND = {"ranked list": "ranked_list", "short list": "short_list", "shortlist": "short_list",
               "answer key": "answer_key", "interview": "interview", "result": "result"}


def _cats(s: str) -> list[str]:
    from examradar_extraction.rules_kpsc import cats_in

    out = cats_in(s)
    # "Cat.No.165&166/2026" lists several numbers sharing one year.
    for m in re.finditer(r"(\d{1,3})((?:\s*[&,]\s*\d{1,3})+)\s*/\s*(\d{4})", s):
        for n in [m.group(1)] + re.findall(r"\d{1,3}", m.group(2)):
            c = f"{int(n):03d}/{m.group(3)}"
            if c not in out:
                out.append(c)
    return sorted(out, key=lambda c: (c[-4:], int(c.split("/")[0])))


class KeralaPSC(Adapter):
    key = "kerala_psc"
    sector = "psc"

    def parse_listing(self, listing: Listing, body: bytes, base_url: str) -> list[Item]:
        path = urlparse(listing.url).path
        if path.startswith("/notifications"):
            return self._notifications(body, base_url)
        if path.startswith("/examinations"):
            return self._programmes(body, base_url)
        if path.startswith("/latest"):
            return self._latest(body, base_url)
        return [i for i in generic_anchor_items(body, base_url, self.content_hosts()) if i.doc_urls]

    def _notifications(self, body: bytes, base: str) -> list[Item]:
        from examradar_extraction.dates import parse_date
        from examradar_extraction.rules_kpsc import expand_cat_range

        items = []
        for tr in soup_of(body).select("table tr"):
            tds = tr.find_all("td")
            if len(tds) < 3 or not tds[0].find("a"):
                continue
            title, cat_text, last = clean(tds[0].get_text()), clean(tds[1].get_text()), clean(tds[2].get_text())
            url = normalise_url(tds[0].find("a")["href"], base)
            cats = expand_cat_range(cat_text)
            facts = []
            gd, ld = parse_date(title), parse_date(last)
            if gd:
                facts.append(Fact("event", {"event_type": "notification", "date": gd.value.isoformat(), "category_numbers": cats,
                                            "precision": "day", "certainty": "official"}, title, None, 0.95, "rule"))
            if ld:
                facts.append(Fact("event", {"event_type": "application_end", "date": ld.value.isoformat(), "category_numbers": cats,
                                            "precision": "day", "certainty": "official"}, f"{cat_text} | {last}", None, 0.95, "rule"))
            items.append(Item(key=f"gazette:{url}", title=f"{title} — {cat_text}", url=url, kind="notification",
                              facts=facts, follow=[url], data={"category_numbers": cats}))
        return items

    def parse_detail(self, url: str, body: bytes) -> list[Item]:
        items = []
        for a in soup_of(body).select("a[href$='.pdf'], a[type^='application/pdf']"):
            title = clean(a.get_text())
            cats = _cats(title)
            if not cats:
                continue
            href = normalise_url(a["href"], url)
            items.append(Item(key=href, title=title, url=href, kind="notification", doc_urls=[href],
                              cycle=self._hint_from_title(title, cats)))
        return items

    def _hint_from_title(self, title: str, cats: list[str]) -> CycleHint:
        base = re.sub(r"\(\s*Cat\.?\s*No.*$", "", title, flags=re.I).strip(" -")
        post, _, dept = base.partition(" - ")
        post = clean(post)
        return CycleHint(exam_slug=f"kpsc-{slugify(post)}", exam_name=post, title=f"{base} (Cat. No. {', '.join(cats)})",
                         sector="psc", year=int(cats[0][-4:]), notification_number="Cat. No. " + ", ".join(cats),
                         category_numbers=cats)

    def cycle_for_category(self, cat: str, post: str | None, department: str | None) -> CycleHint:
        name = clean(post) or f"Category {cat}"
        title = f"{name} - {clean(department)}" if department else name
        return CycleHint(exam_slug=f"kpsc-{slugify(name)}", exam_name=name, title=f"{title} (Cat. No. {cat})", sector="psc",
                         year=int(cat[-4:]), notification_number=f"Cat. No. {cat}", category_numbers=[cat])

    def _programmes(self, body: bytes, base: str) -> list[Item]:
        items = []
        for a in soup_of(body).find_all("a", href=True):
            title = clean(a.get_text())
            if "programme" in title.lower() and a["href"].lower().endswith(".pdf"):
                href = normalise_url(a["href"], base)
                items.append(Item(key=href, title=title, url=href, kind="schedule", doc_urls=[href]))
        return items

    def _latest(self, body: bytes, base: str) -> list[Item]:
        from examradar_extraction.dates import find_dates

        items = []
        for tr in soup_of(body).select("table tr"):
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue
            typ, title, detail = clean(tds[1].get_text()), clean(tds[2].get_text()), clean(tds[3].get_text())
            link = tds[4].find("a", href=True)
            href = normalise_url(link["href"], base) if link else None
            kind = next((v for k, v in LATEST_KIND.items() if k in typ.lower()), "notice")
            cats = _cats(title)
            facts = []
            wef = re.search(r"wef\s*([\d./-]{8,10})", detail, re.I)
            if wef and kind in ("ranked_list", "short_list") and cats:
                d = find_dates(wef.group(1))
                if d:
                    post = clean(re.sub(r"\(\s*Cat\.?\s*No.*$", "", title, flags=re.I))
                    dept_m = re.search(r"\)\s+in\s+(.+?)\.?$", title)
                    facts.append(Fact("event", {"event_type": kind, "date": d[0].value.isoformat(), "category_numbers": cats,
                                                "post": post or None, "department": clean(dept_m.group(1)) if dept_m else None,
                                                "precision": "day", "certainty": "official"}, wef.group(0), None, 0.9))
            items.append(Item(key=href or f"latest:{typ}:{title}", title=f"{typ}: {title}", url=href, kind=kind,
                              facts=facts, data={"category_numbers": cats}))
        return items

    def doc_options(self, item: Item) -> dict:
        return {"tables": item.kind == "schedule"}

    def extract(self, item: Item, doc) -> list[Fact]:
        from examradar_extraction import rules_kpsc
        from examradar_extraction.rules import event_facts

        if item.kind == "schedule":
            return rules_kpsc.programme_facts(doc, item.title)
        if item.kind == "notification":
            return rules_kpsc.notification_facts(doc)
        return event_facts(doc)
