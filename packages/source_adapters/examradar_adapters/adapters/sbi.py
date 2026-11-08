import re

from ..base import Adapter, CycleHint, Fact, Item, Listing, classify_text, clean, slugify, soup_of
from ..normalise import normalise_url

RE_WINDOW = re.compile(r"(?:apply online|online registration)[^()]{0,20}\(?\s*(?:from\s*)?(\d{2}\.\d{2}\.\d{4})\s*(?:to|TO|-)\s*(\d{2}\.\d{2}\.\d{4})", re.I)
RE_EXTENDED = re.compile(r"extended\s+(?:till|upto|up to)\s+(\d{2}\.\d{2}\.\d{4})", re.I)


class SBI(Adapter):
    key = "sbi"
    sector = "banking"

    def parse_listing(self, listing: Listing, body: bytes, base_url: str) -> list[Item]:
        from examradar_extraction.dates import parse_date

        soup = soup_of(body)
        items: list[Item] = []
        for head in soup.select("div.accordion[data-target]"):
            content = soup.select_one(head["data-target"])
            if content is None:
                continue
            adv = clean(head.get("data-articleid", ""))
            ps = [clean(p.get_text(" ")) for p in head.find_all("p")]
            title = re.sub(r"\(\s*(?:apply online|online registration).*?\)+", "", ps[0], flags=re.I).strip() if ps else adv
            hint = CycleHint(exam_slug=f"sbi-{slugify(re.sub(r'ON REGULAR BASIS|ON CONTRACT(UAL)? BASIS', '', title, flags=re.I))}",
                             exam_name=title.title(), title=f"{title.title()} ({adv})", sector="banking",
                             year=None, notification_number=adv)
            facts: list[Fact] = []
            labels = [clean(a.get_text(" ")) for a in content.find_all("a", href=True)] + ps
            for lab in labels:
                w = RE_WINDOW.search(lab)
                if w and not any(f.value.get("event_type") == "application_start" for f in facts):
                    a, b = parse_date(w.group(1)), parse_date(w.group(2))
                    if a and b:
                        for et, d in (("application_start", a), ("application_end", b)):
                            facts.append(Fact("event", {"event_type": et, "date": d.value.isoformat(), "precision": "day",
                                                        "certainty": "official"}, w.group(0), None, 0.92))
                e = RE_EXTENDED.search(lab)
                if e and (d := parse_date(e.group(1))):
                    facts = [f for f in facts if f.value.get("event_type") != "application_end"]
                    facts.append(Fact("event", {"event_type": "application_end", "date": d.value.isoformat(), "precision": "day",
                                                "certainty": "official", "extended": True}, e.group(0), None, 0.92))
            docs, children = [], []
            for a in content.find_all("a", href=True):
                lab = clean(a.get_text(" "))
                href = normalise_url(a["href"], base_url)
                if re.search(r"apply", lab, re.I) and not href.lower().endswith(".pdf"):
                    facts.append(Fact("link", {"kind": "apply", "url": href, "label": lab}, lab, None, 0.95))
                elif href.lower().split("?")[0].endswith(".pdf"):
                    row = clean(a.find_parent("li").get_text(" ")) if a.find_parent("li") else lab
                    if re.search(r"advertisement|advt|english", row, re.I) and not re.search(r"hindi|biodata|ctc|undertaking", lab, re.I):
                        docs.append(href)
                    elif not re.search(r"hindi|biodata|ctc|undertaking|format", lab + row, re.I):
                        children.append(Item(key=href, title=f"{title.title()}: {lab}", url=href, kind=classify_text(lab),
                                             doc_urls=[href], cycle=hint))
                elif re.search(r"call letter|result|admit", lab, re.I):
                    facts.append(Fact("link", {"kind": classify_text(lab), "url": href, "label": lab}, lab, None, 0.9))
            items.append(Item(key=f"sbi:{adv or title}", title=title.title(), url=listing.url, kind="notification",
                              doc_urls=docs[:1], facts=facts, cycle=hint, data={"advertisement": adv}))
            items.extend(children)
        return items

    def extract(self, item: Item, doc) -> list[Fact]:
        from examradar_extraction.rules import event_facts, generic_facts

        return generic_facts(doc) if item.kind == "notification" else event_facts(doc)
