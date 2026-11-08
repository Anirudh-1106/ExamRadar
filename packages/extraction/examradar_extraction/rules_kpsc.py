"""Kerala PSC: numbered notification clauses and exam programme tables."""

import re
from typing import Any

from examradar_adapters.base import Fact

from .dates import find_dates
from .pdf import DocText, flat
from .rules import age_facts, event_facts

CAT_RX = re.compile(r"\b(\d{1,3})\s*/\s*(\d{4})\b")


def norm_cat(n: str, y: str) -> str:
    return f"{int(n):03d}/{y}"


def cats_in(s: str) -> list[str]:
    return [norm_cat(a, b) for a, b in CAT_RX.findall(s)]


def expand_cat_range(s: str) -> list[str]:
    """'CAT.NO.162/2026 TO 173/2026' -> 162/2026 ... 173/2026."""
    m = re.search(r"(\d{1,3})\s*/\s*(\d{4})\s*(?:TO|-|–)\s*(?:CAT\.?\s*NO\.?\s*:?\s*)?(\d{1,3})\s*/\s*(\d{4})", s, re.I)
    if m and m.group(2) == m.group(4) and 0 <= int(m.group(3)) - int(m.group(1)) <= 200:
        return [norm_cat(str(i), m.group(2)) for i in range(int(m.group(1)), int(m.group(3)) + 1)]
    return cats_in(s)


def notification_facts(doc: DocText) -> list[Fact]:
    text_all = " ".join(flat(p) for p in doc.pages)
    facts: list[Fact] = []
    first = flat(doc.pages[0]) if doc.pages else ""
    m = re.search(r"CATEGORY\s*No\.?\s*:?\s*(\d{1,3})\s*/\s*(\d{4})", first, re.I)
    if m:
        facts.append(Fact("notification_number", {"number": norm_cat(m.group(1), m.group(2))}, m.group(0), 1, 0.95))
    post = re.search(
        r"Name of (?:the )?post\s*:\s*(.+?)\s+\d{1,2}\s*\.\s*Scale of Pay\s*:\s*(.+?)\s+\d{1,2}\s*\.\s*Number of Vacanc(?:y|ies)\s*:\s*(.+?)\s+(?:Note|\d{1,2}\s*\.)",
        text_all, re.I)
    dept = re.search(r"Name of (?:the )?(?:concern|Department|Company|Board|Corporation|Institution)\s*:\s*(.+?)\s+\d{1,2}\s*\.\s*Name of (?:the )?post",
                     text_all, re.I)
    if post:
        vac_text = post.group(3).strip()
        vm = re.match(r"(\d{1,4})", vac_text)
        value: dict[str, Any] = {"name": post.group(1).strip(), "pay_scale": post.group(2).strip(), "vacancies_text": vac_text,
                                 "vacancies": int(vm.group(1)) if vm else None}
        if dept:
            value["department"] = dept.group(1).strip()
        start = dept.start() if dept else post.start()
        quote = text_all[start: post.end()]
        facts.append(Fact("post", value, quote, doc.page_of(text_all.find(post.group(1))), 0.9))
        if value["vacancies"] is not None:
            facts.append(Fact("vacancies", {"total": value["vacancies"]}, post.group(0)[-120:].strip(), None, 0.85))
    q = re.search(r"Qualifications?\s*:?-?\s*(.{10,600}?)\s+(?:Link-|Note\s*:|\d{1,2}\s*\.\s*Mode of submitting)", text_all, re.I)
    if q:
        facts.append(Fact("qualification", {"text": q.group(1).strip()}, q.group(0)[: len(q.group(0))].strip(), None, 0.85))
    rel = re.search(r"Candidates belonging to (.{5,80}?) (?:are|is) eligible\s+for\s+usual age relaxation", text_all, re.I)
    if rel:
        groups = []
        for g, code in (("backward", "OBC"), ("SC", "SC"), ("ST", "ST")):
            if re.search(g, rel.group(1), re.I):
                groups.append(code)
        facts.append(Fact("relaxation_reference", {"categories": groups, "where": "Part II General Conditions"}, rel.group(0), None, 0.85))
    facts += age_facts(doc)
    facts += [f for f in event_facts(doc) if f.value["event_type"] in ("application_end", "exam")]
    return facts


HEADER_KEYS = {
    "cat": ("cat",),
    "post": ("nameofpost", "post"),
    "department": ("department",),
    "scope": ("statewide", "district"),
    "exam_date": ("dateofexamination", "dateofexam"),
    "admit": ("admission", "hallticket"),
    "confirmation": ("dateofconfirmation", "confirmation"),
    "mode": ("modeofexam",),
}


def _map_header(row: list[str]) -> dict[str, int]:
    keys: dict[str, int] = {}
    for idx, cell in enumerate(row):
        c = re.sub(r"[^a-z]", "", (cell or "").lower())
        for k, pats in HEADER_KEYS.items():
            if k not in keys and any(p in c for p in pats):
                if k == "post" and "cat" in keys and keys["cat"] == idx:
                    continue
                keys[k] = idx
                break
    return keys


def respace(cell: str, page_text: str) -> str:
    """Table cells lose their spaces ('ASSISTANTDIRECTOROF'). Recover the spaced form from the page text."""
    compact = re.sub(r"\s+", "", cell)
    if not compact:
        return ""
    rx = re.compile(r"\s*".join(re.escape(c) for c in compact[:120]))
    m = rx.search(page_text)
    return re.sub(r"\s+", " ", m.group(0)).strip() if m else re.sub(r"\s+", " ", cell).strip()


def programme_facts(doc: DocText, title: str) -> list[Fact]:
    """Rows of a monthly exam programme. Each cell value in the quote is checked against the page text."""
    for_confirmation = bool(re.search(r"for submitting confirmation", title, re.I))
    finalised = bool(re.search(r"finali[sz]ed", title, re.I))
    facts: list[Fact] = []
    last_hdr: dict[str, int] | None = None
    last_cols = 0
    for pidx, tables in sorted(doc.tables.items()):
        page_text = doc.pages[pidx] if pidx < len(doc.pages) else ""
        for table in tables:
            if not table:
                continue
            hdr = _map_header(table[0])
            rows = table[1:]
            if "cat" not in hdr or "exam_date" not in hdr:
                # Continuation pages repeat the table without a header row.
                if last_hdr is None or len(table[0]) != last_cols:
                    continue
                hdr, rows = last_hdr, table
            last_hdr, last_cols = hdr, len(table[0])
            # A common test spans several rows with one merged cell for its dates; empty cells inherit from the row above.
            carry: dict[str, str] = {}
            for row in rows:
                def cell(k: str, row: list[str] = row, hdr: dict[str, int] = hdr, carry: dict[str, str] = carry) -> str:
                    i = hdr.get(k)
                    v = (row[i] or "").strip() if i is not None and i < len(row) else ""
                    if k in ("exam_date", "admit", "confirmation"):
                        if v:
                            carry[k] = v
                        elif cats_in(cell("cat")):
                            v = carry.get(k, "")
                    return v
                cats = cats_in(cell("cat"))
                exam = find_dates(cell("exam_date"))
                if not cats or not exam:
                    continue
                post = respace(cell("post"), page_text)
                base = {"category_numbers": cats, "post": post, "department": re.sub(r"\s+", " ", cell("department")),
                        "programme": "for_confirmation" if for_confirmation else ("finalised" if finalised else "programme")}
                facts.append(Fact("event", {**base, "event_type": "exam", "date": exam[0].value.isoformat(),
                                            "precision": "day", "certainty": "official"},
                                  " | ".join([cell("cat"), cell("exam_date").split("\n")[0]]), pidx + 1, 0.9, "table"))
                adm = find_dates(cell("admit"))
                if adm:
                    facts.append(Fact("event", {**base, "event_type": "admit_card", "date": adm[0].value.isoformat(),
                                                "precision": "day", "certainty": "official"},
                                      " | ".join([cell("cat"), cell("admit")]), pidx + 1, 0.9, "table"))
                conf = cell("confirmation")
                cd = find_dates(conf)
                if cd:
                    if len(cd) > 1:
                        base = {**base, "window_start": cd[0].value.isoformat()}
                    facts.append(Fact("event", {**base, "event_type": "confirmation_deadline", "date": cd[-1].value.isoformat(),
                                                "precision": "day", "certainty": "official"},
                                      " | ".join([cell("cat"), conf]), pidx + 1, 0.9, "table"))
                elif conf:
                    facts.append(Fact("confirmation_note", {**base, "text": re.sub(r"\s+", " ", conf)},
                                      " | ".join([cell("cat"), conf]), pidx + 1, 0.9, "table"))
    return facts


def general_conditions_facts(doc: DocText) -> list[Fact]:
    """Age concessions from Kerala PSC's General Conditions (Part II), which notifications refer to as 'usual age relaxation'.

    Firm rules give a clear answer. Rules that depend on facts the app does not collect (length of service, widowhood,
    type of disability, special qualification cases) are marked conditional and lead to 'check before applying'.
    """
    text = " ".join(flat(p) for p in doc.pages)
    facts: list[Fact] = []

    def add(value: dict[str, Any], m: "re.Match[str]") -> None:
        facts.append(Fact("relaxation", value, m.group(0), doc.page_of(text.find(m.group(0)[:40])), 0.95))

    cap = re.search(r"maximum age limit shall in no case exceed 50 \(fifty\) years", text, re.I)
    if cap:
        facts.append(Fact("relaxation_cap", {"cap_age": 50}, cap.group(0), None, 0.95))
    m = re.search(r"The upper age limit prescribed shall be raised by five years in the case of candidates belonging to any of the "
                  r"Scheduled Castes.{0,200}?Scheduled Tribes and by three years in the case of candidates belonging to any of the "
                  r"Other Backward Classes", text, re.I)
    if m:
        for grp, yrs in (("SC", 5), ("ST", 5), ("OBC", 3)):
            add({"applies_to": grp, "years": yrs}, m)
    m = re.search(r"The maximum age limit laid down for appointment to any post shall not apply in the case of candidates belonging to "
                  r"any of the Scheduled Caste", text, re.I)
    if m:
        for grp in ("SC", "ST"):
            add({"applies_to": grp, "years": 99, "conditional": True,
                 "note": "In some cases the upper age limit does not apply to SC/ST candidates (General Conditions 2(ii) to 2(iv))."}, m)
    m = re.search(r"relaxed in the case of Ex-servicemen to the extent of the period of service.{0,120}?up to a maximum of five years", text, re.I)
    if m:
        add({"applies_to": "EXSM", "years": 5, "conditional": True, "note": "Ex-servicemen: up to five years, depending on service."}, m)
    m = re.search(r"Age concession upto 15 years will be granted to candidates belonging to Blindness and Low Vision and Deaf and hard of "
                  r"hearing categories.{0,120}?and 10 years to candidates belonging to Locomotor disability", text, re.I)
    if m:
        add({"applies_to": "PWBD", "years": 10}, m)
        add({"applies_to": "PWBD", "years": 15, "conditional": True,
             "note": "15 years for blindness, low vision, deafness or hard of hearing; 10 years for other listed disabilities."}, m)
    m = re.search(r"upper age limit prescribed in the Special Rules, shall be further raised by five years in the case of widows", text, re.I)
    if m:
        add({"applies_to": "FEMALE", "years": 5, "conditional": True, "note": "Widows: five more years."}, m)
    return facts
