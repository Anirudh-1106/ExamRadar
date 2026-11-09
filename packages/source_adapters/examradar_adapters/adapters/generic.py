"""Configurable adapter for official sites with a plain list of notices. A new source needs only config/sources.yaml.

Options (all optional) under an organisation in sources.yaml:
  render: [urls]            listing URLs that need a headless browser (JavaScript-only sites)
  rows: "css selector"      elements that each hold one notice (default: every link)
  include: "regex"          keep notices whose title matches (default: recruitment and exam words)
  exclude: "regex"          drop notices whose title matches
  follow: true              open HTML notice pages on the same site to find their PDFs
  table: {title: n, number: n, start: n, end: n}   column numbers for listing tables with dates
  grid: {title: cls, number: cls, start: cls, end: cls}   class names for card or grid layouts with dates
  max_age_days: n           ignore listed recruitments whose last date (or start date, if no last date) is older than this
  recent_years: n           ignore undated notices whose title or number names only years before (this year - n)
  docs_only: true           keep only links to documents (PDFs), not pages
  page_dates: true          read a key-dates block printed on the listing page and give it to the latest session
  cycle: {mode: per_item | family | none, family: "CTET", session: "regex with (month) and (year) groups"}
  sector: teaching | engineering | banking | other ...
"""

import re
from typing import Any
from urllib.parse import unquote, urlparse

from ..base import Adapter, CycleHint, Fact, Item, Listing, classify_text, clean, slugify, soup_of
from ..http import FetchResult, PoliteClient, render_page
from ..normalise import normalise_url

DEFAULT_INCLUDE = (r"recruit|notification|vacanc|advertis|walk.?in|engagement|apprentice|exam|test|admit|hall ticket|answer key|"
                   r"result|rank|short.?list|interview|selection|schedule|syllabus|prospectus|bulletin|application|post of|posts of")
NOISE = r"tender|quotation|auction|\brti\b|annual report|budget|pension|press release|photo gallery|e-?office|earnings call"
LINK_WORDS = r"(click here|download|view|more details?|read more|details|english|hindi|pdf)[^a-z]*"
SESSION = (r"(JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|APR(?:IL)?|MAY|JUNE?|JULY?|AUG(?:UST)?|SEPT?(?:EMBER)?|OCT(?:OBER)?|"
           r"NOV(?:EMBER)?|DEC(?:EMBER)?)[\s,.-]*(20\d{2})")


def _series(number: str | None) -> tuple[str, int] | None:
    """'VSSC-301', 'VSSC – 294', 'NO. 288' -> ('VSSC', 301) ... ; numbers with a year or several parts -> None."""
    m = re.fullmatch(r"\s*([A-Za-z][A-Za-z.]*)\s*[-–:.]?\s*(\d{1,4})\s*", number or "")
    return (m.group(1).upper().rstrip("."), int(m.group(2))) if m else None


class Generic(Adapter):
    key = "generic"

    def fetch(self, client: PoliteClient, url: str, etag: str | None = None, last_modified: str | None = None) -> FetchResult:
        if url in self.cfg.get("render", []):
            return render_page(client, url)
        return client.get(url, etag=etag, last_modified=last_modified)

    def _ok_url(self, url: str) -> bool:
        p = urlparse(url)
        return any(d["host"] == p.netloc and p.path.startswith(d.get("path_prefix", "/")) for d in self.cfg.get("domains", []))

    def _keep(self, title: str) -> bool:
        inc = re.compile(self.cfg.get("include", DEFAULT_INCLUDE), re.I)
        exc = self.cfg.get("exclude")
        return bool(inc.search(title)) and not re.search(NOISE, title, re.I) and not (exc and re.search(exc, title, re.I))

    def _too_old(self, title: str) -> bool:
        """recent_years: n drops notices whose title names only years before (this year - n)."""
        from datetime import date

        n = self.cfg.get("recent_years")
        years = [int(y) for y in re.findall(r"(?<!\d)(20\d{2})(?!\d)", title)]
        return bool(n is not None and years and max(years) < date.today().year - int(n))

    def parse_listing(self, listing: Listing, body: bytes, base_url: str) -> list[Item]:
        items: list[Item] = []
        if self.cfg.get("grid"):
            items = self._grid(body, base_url)
        if not items and self.cfg.get("table"):
            items = self._table(body, base_url)
        if not items:
            items = self._rows(body, base_url)
        if self.cfg.get("page_dates"):
            self._page_dates(body, items)
        return items

    def _page_dates(self, body: bytes, items: list[Item]) -> None:
        """page_dates: true reads a key-dates block printed on the listing page itself ("Submission of Online
        Application from : 23/09/2026 to 03/10/2026 ... Date of Examinations: 14/11/2026") and gives it to the latest
        session in the listing, only when the dates fall in that session's year."""
        from examradar_extraction.pdf import DocText
        from examradar_extraction.rules import event_facts

        from ..normalise import main_text

        facts = event_facts(DocText([main_text(body)]))
        sessions = [i for i in items if i.cycle and i.cycle.year]
        if not facts or not sessions:
            return
        months = "jan feb mar apr may jun jul aug sep oct nov dec".split()

        def order(i: Item) -> tuple[int, int]:
            label = (i.cycle.title if i.cycle else "").lower()
            return (i.cycle.year or 0 if i.cycle else 0, max((n for n, m in enumerate(months) if m in label), default=-1))

        latest = max(sessions, key=order)
        first_year = min(int(f.value["date"][:4]) for f in facts)
        if latest.cycle and first_year == latest.cycle.year:
            have = {(f.value.get("event_type"), f.value.get("date")) for f in latest.facts}
            latest.facts.extend(f for f in facts if (f.value["event_type"], f.value["date"]) not in have)

    def _rows(self, body: bytes, base_url: str) -> list[Item]:
        soup = soup_of(body)
        for t in soup(["nav", "header", "footer", "script", "style"]):
            t.decompose()
        sel = self.cfg.get("rows")
        containers = soup.select(sel) if sel else []
        pairs: list[tuple[Any, Any]] = ([(c, a) for c in containers for a in c.find_all("a", href=True)[:3]] if containers
                                        else [(None, a) for a in soup.find_all("a", href=True)])
        items: dict[str, Item] = {}
        if containers and self.cfg.get("no_links"):
            # Rows whose links are script handlers ("#"): the notice is the row text; link to the official listing page.
            from datetime import datetime

            for c in containers:
                title = clean(c.get_text(" "))
                pub = None
                if self.cfg.get("published") and (m := re.search(self.cfg["published"], title)):
                    try:
                        pub = datetime.fromisoformat(m.group(1))
                    except ValueError:
                        pub = None
                    title = clean(title.replace(m.group(0), ""))
                if len(title) < 12 or not self._keep(title) or self._too_old(title):
                    continue
                key = "row:" + title[:300]
                items[key] = Item(key=key, title=title[:400], url=base_url, kind=classify_text(title), published_hint=pub,
                                  cycle=self.hint(title), data={"fetch": False})
            return list(items.values())
        for c, a in pairs:
            href = str(a["href"]).strip()
            if href.startswith(("javascript:", "mailto:", "#", "tel:")):
                continue
            url = normalise_url(href, base_url)
            if not self._ok_url(url):
                continue
            title = clean(a.get_text(" "))
            if len(title) < 15 or re.fullmatch(LINK_WORDS, title, re.I):
                # Generic link text: a descriptive file name ("K-TET September 2026-Notification.pdf") beats a page blob.
                fname = clean(re.sub(r"[_+]", " ", unquote(urlparse(url).path.rsplit("/", 1)[-1].rsplit(".", 1)[0])))
                holder = c if c is not None else a.find_parent(["tr", "li", "article", "p"])
                around = clean(holder.get_text(" ")) if holder is not None else ""
                if len(re.findall(r"[A-Za-z]{3,}", fname)) >= 3 and (len(around) > 200 or len(around) < 25):
                    title = fname
                elif around:
                    title = around
            title = re.sub(r"\s*(read more|more details|click here|download|view)\s*$", "", title, flags=re.I)[:400]
            if len(title) < 12 or not self._keep(title) or self._too_old(title):
                continue
            is_doc = url.lower().split("?")[0].endswith((".pdf", ".doc", ".docx"))
            if self.cfg.get("docs_only") and not is_doc:
                continue
            if url not in items:
                items[url] = Item(key=url, title=title, url=url, kind=classify_text(title), doc_urls=[url] if is_doc else [],
                                  follow=[url] if (not is_doc and self.cfg.get("follow")) else [], cycle=self.hint(title))
        return list(items.values())

    def _table(self, body: bytes, base_url: str) -> list[Item]:
        cols = self.cfg["table"]
        need = max(v for v in cols.values() if isinstance(v, int))
        out = []
        for tr in soup_of(body).select("table tr"):
            tds = tr.find_all("td")
            if len(tds) <= need:
                continue
            cell = [clean(td.get_text(" ")) for td in tds]
            title = cell[cols["title"]]
            if len(title) < 10 or not self._keep(title):
                continue
            link = tr.find("a", href=True)
            url = normalise_url(str(link["href"]), base_url) if link else base_url
            if not self._ok_url(url):
                url = base_url
            number = cell[cols["number"]] if "number" in cols else None
            it = self._dated_item(title, number or None, url, base_url, cell[cols["start"]] if "start" in cols else "",
                                  cell[cols["end"]] if "end" in cols else "")
            if it:
                out.append(it)
        return out

    def _dated_item(self, title: str, number: str | None, url: str, base_url: str, start: str, end: str) -> Item | None:
        from datetime import date, timedelta

        from examradar_extraction.dates import find_dates

        facts = []
        end_d = None
        for raw, et in ((start, "application_start"), (end, "application_end")):
            d = find_dates(raw) if raw else []
            if d:
                if et == "application_end":
                    end_d = d[0].value
                facts.append(Fact("event", {"event_type": et, "date": d[0].value.isoformat(), "precision": d[0].precision,
                                            "certainty": "official"}, f"{title[:120]} | {raw}", None, 0.9))
        age = self.cfg.get("max_age_days")
        if age and end_d and end_d < date.today() - timedelta(days=int(age)):
            return None
        if not end_d:
            starts = [f.value["date"] for f in facts if f.value["event_type"] == "application_start"]
            if age and starts and date.fromisoformat(starts[0]) < date.today() - timedelta(days=int(age)):
                return None
            if not facts and self._too_old(f"{title} {number or ''}"):
                return None  # undated, and the title or advertisement number names only old years
        is_doc = url.lower().split("?")[0].endswith(".pdf")
        return Item(key=number or title, title=title, url=url, kind="notification" if facts else classify_text(title),
                    doc_urls=[url] if is_doc else [], facts=facts, cycle=self.hint(title, number),
                    follow=[url] if (not is_doc and url != base_url and self.cfg.get("follow")) else [])

    def _grid(self, body: bytes, base_url: str) -> list[Item]:
        from datetime import date, timedelta

        from examradar_extraction.dates import find_dates

        g = self.cfg["grid"]
        out: list[Item] = []
        expired: dict[str, int] = {}
        titles = soup_of(body).find_all(class_=g["title"])
        for i, t in enumerate(titles):
            title = clean(t.get_text(" "))
            # An entry's cells are the elements between its title and the next title; never read a neighbour's cells.
            stop = titles[i + 1] if i + 1 < len(titles) else None
            cells = []
            for el in t.next_elements:
                if el is stop:
                    break
                if getattr(el, "name", None):
                    cells.append(el)

            def of(cls: str | None, cells: list = cells) -> list[str]:
                return [clean(e.get_text(" ")) for e in cells if cls and cls in (e.get("class") or [])]

            nums = of(g.get("number"))
            start, end = (of(g.get("start")) or [""])[0], (of(g.get("end")) or [""])[0]
            if not (start or end):
                # Some sections put the open and close dates in cells styled like the number.
                dated = [n for n in nums[1:] if find_dates(n)]
                if len(dated) >= 2:
                    start, end = dated[0], dated[1]
            link = next((e for e in cells if e.name == "a" and e.get("href")), None)
            url = normalise_url(str(link["href"]), base_url) if link else base_url
            if not self._ok_url(url):
                url = base_url
            number = (nums[0] if nums else "") or None
            ends = find_dates(end) if end else []
            ser = _series(number)
            if ser and ends and self.cfg.get("max_age_days") and ends[0].value < date.today() - timedelta(days=int(self.cfg["max_age_days"])):
                expired[ser[0]] = max(expired.get(ser[0], 0), ser[1])
            if len(title) < 10 or not self._keep(title):
                continue
            it = self._dated_item(title, number, url, base_url, start, end)
            if it:
                out.append(it)
        # An undated advertisement numbered below an expired one of the same series ("VSSC-301" under an expired
        # "VSSC-322") is older still.
        return [it for it in out if it.facts or not (ser := _series(it.key)) or ser[1] > expired.get(ser[0], -1)]

    def parse_detail(self, url: str, body: bytes) -> list[Item]:
        soup = soup_of(body)
        page_title = clean((soup.find("h1") or soup.title or soup).get_text(" "))[:300]
        # Drop breadcrumbs ("... Home / Careers") so the notice joins the same exam as its listing entry.
        page_title = re.sub(r"\s+Home\s*[/>»|].*$", "", page_title)
        out = []
        for a in soup.find_all("a", href=True):
            href = normalise_url(str(a["href"]), url)
            if href.lower().split("?")[0].endswith(".pdf") and self._ok_url(href):
                label = clean(a.get_text(" "))
                out.append(Item(key=href, title=f"{page_title}: {label}"[:500] if label else page_title, url=href,
                                kind=classify_text(page_title + " " + label), doc_urls=[href], cycle=self.hint(page_title)))
        return out[:6]

    def hint(self, title: str, number: str | None = None) -> CycleHint | None:
        c = self.cfg.get("cycle", {"mode": "per_item"})
        org, sector = self.org_key, self.cfg.get("sector", "other")
        if c.get("mode") == "none":
            return None
        if c.get("mode") == "family":
            m = re.search(c.get("session", SESSION), title, re.I)
            if not m:
                return None
            fam = c["family"]
            label = f"{m.group(1).title()[:3]} {m.group(2)}"
            return CycleHint(exam_slug=f"{org}-{slugify(fam)}", exam_name=fam, title=f"{fam} {label}", sector=sector, year=int(m.group(2)))
        core = re.sub(r"\b(notification|corrigendum|addendum|extension|date extended|regarding|reg\.?|public notice|notice)\b[:\- ]*", "",
                      title, flags=re.I)
        core = re.sub(r"\s*\(?\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\)?", "", core)
        # "for recruitment to the post of X" -> "X"
        core = re.sub(r"^\W*(?:\d+\s*[–-]\s*)?(?:for\s+)?(?:direct\s+)?(?:(?:recruitment|selection|engagement)\b)?\s*(?:(?:for|to|of)\b)?\s*"
                      r"(?:selection\s+to\s+)?(?:the\s+)?(?:posts?\s+of\s+)?", "", core, flags=re.I)
        core = clean(re.sub(r"[-–:|]+\s*$", "", core))[:160]
        if len(core) < 10:
            return None
        year = re.search(r"20\d{2}", title)
        return CycleHint(exam_slug=f"{org}-{slugify(core)[:90]}", exam_name=core, title=core, sector=sector,
                         year=int(year.group(0)) if year else None, notification_number=number)

    def extract(self, item: Item, doc: Any) -> list[Fact]:
        from examradar_extraction.rules import event_facts, generic_facts

        return generic_facts(doc) if item.kind in ("notification", "corrigendum", "notice") else event_facts(doc)
