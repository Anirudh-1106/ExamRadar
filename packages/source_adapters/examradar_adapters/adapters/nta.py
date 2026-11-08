import re
from datetime import datetime
from urllib.parse import urlparse

from ..base import Adapter, CycleHint, Item, Listing, classify_text, clean, soup_of
from ..normalise import normalise_url

RE_STAMP = re.compile(r"Notice_(\d{14})\.pdf", re.I)


def hint_for(title: str, year: int | None) -> CycleHint | None:
    t = title.upper()
    session = re.search(r"(JUNE|DECEMBER|JAN(?:UARY)?|JULY)[\s,-]*(20\d{2})", t)
    label = f"{session.group(1).title()} {session.group(2)}" if session else (str(year) if year else "")
    yr = int(session.group(2)) if session else year
    if "CSIR" in t and "NET" in t:
        return CycleHint("nta-csir-ugc-net", "Joint CSIR-UGC NET", f"Joint CSIR-UGC NET {label}".strip(), "teaching", yr)
    if "UGC" in t and "NET" in t:
        return CycleHint("nta-ugc-net", "UGC-NET", f"UGC-NET {label}".strip(), "teaching", yr)
    return None


def keyword_match(title: str, keywords: list[str]) -> bool:
    low = title.lower()
    return any(re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", low) for k in keywords)


class NTA(Adapter):
    key = "nta"
    sector = "teaching"

    def parse_listing(self, listing: Listing, body: bytes, base_url: str) -> list[Item]:
        include = [k.lower() for k in self.cfg.get("include_keywords", [])]
        hosts = self.content_hosts()
        items: dict[str, Item] = {}
        for a in soup_of(body).find_all("a", href=True):
            href = normalise_url(a["href"], base_url)
            if not href.lower().endswith(".pdf") or urlparse(href).netloc not in hosts:
                continue
            holder = a.find_parent("p") or a.find_parent("li") or a.parent
            content = holder.find("content") if holder else None
            title = clean((content or holder or a).get_text(" "))
            title = re.sub(r"\s*Read More\s*$", "", title)
            if len(title) < 12 or (include and not keyword_match(title, include)):
                continue
            stamp = RE_STAMP.search(href)
            published = datetime.strptime(stamp.group(1), "%Y%m%d%H%M%S") if stamp else None
            items[href] = Item(key=href, title=title, url=href, kind=classify_text(title), doc_urls=[href],
                               published_hint=published, cycle=hint_for(title, published.year if published else None))
        return list(items.values())
