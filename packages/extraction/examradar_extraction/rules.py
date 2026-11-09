"""Source-independent rule extractors. Each fact carries the exact quote it came from."""

import re
from typing import Any

from examradar_adapters.base import Fact

from .dates import find_dates, find_range
from .pdf import DocText, flat

POINT, RANGE = "point", "range"

EVENT_LABELS: list[tuple[str, str, str]] = [
    ("notification", r"date of (?:notification|publication)(?: of (?:the )?examination)?|date of advertisement", POINT),
    ("application_window",
     r"online registration(?: of application)?(?: and payment of fees?)?(?: including edit/modification of application by candidates)?"
     r"|apply online from|on-?line applications? (?:can be submitted|will be accepted) from"
     r"|submission of (?:the )?on-?line applications?(?: forms?)? from", RANGE),
    ("fee_deadline", r"last date (?:for|of) (?:online )?payment of (?:application )?fees?", POINT),
    # Extension notices: "decided to extend the last date for submission of the Online Application Form ... up to 09th November 2026".
    ("application_end",
     r"(?:extend(?:ed)?|extension of) the (?:last|closing) date (?:for|of) (?:the )?(?:submission|receipt|registration|filling)[^.]{0,160}?"
     r"(?:up ?to|till|until|to)", POINT),
    ("application_end",
     r"last date (?:for|of) (?:the )?(?:receipt|submission|filling up|filling|on-?line submission)?\s?(?:of )?(?:the )?(?:on-?line )?"
     r"(?:applications?|application forms?)|last date to apply|closing date (?:for|of) (?:on-?line )?(?:registration|applications?)"
     r"|last date for (?:on-?line )?registration", POINT),
    ("application_start",
     r"(?:opening|commencement|start(?:ing)?) date (?:of|for) (?:on-?line )?(?:registration|applications?)|registration (?:starts|opens|from)",
     POINT),
    ("fee_window", r"payment of (?:application )?fees?(?:\s*/\s*intimation charges)?(?: \(online\))?", RANGE),
    ("correction_window", r"(?:edit|correction|modification) window|window for (?:correction|modification)", RANGE),
    ("result",
     r"result of (?:the )?(?:online )?examination\s*[–-]\s*(?:preliminary|main)"
     r"|declaration of results?\s*[–-]?\s*(?:preliminary|main) examination", POINT),
    ("exam",
     r"date of (?:\((?:preliminary|main)\) )?(?:the )?(?:written |online )?examination|online examination\s*[–-]\s*(?:preliminary|main)"
     r"|(?:preliminary|main) examination (?:will be held )?on"
     r"|(?:preliminary|main) exam(?:ination)? (?:will be |is )?(?:conducted |held |scheduled )?tentatively"
     r" (?:conducted |held |scheduled )?(?:in|on)(?: the month of)?", POINT),
    ("admit_card",
     r"download of call letters?(?: for online examination)?(?:\s*[–-]\s*(?:preliminary|main))?"
     r"|admission tickets? (?:will be )?available from|admit cards? (?:will be )?(?:available|issued) (?:from|on)"
     r"|download(?:ing)? (?:of )?(?:the )?(?:admit cards?|hall tickets?)(?: through (?:the )?website)?", POINT),
]
_COMPILED = [(t, re.compile(p, re.I), k) for t, p, k in EVENT_LABELS]
TENTATIVE = re.compile(r"tentative|likely|provisional(?:ly)?|expected", re.I)


def _stage(label: str) -> str | None:
    lab = label.lower()
    if "prelim" in lab:
        return "Preliminary"
    if "main" in lab:
        return "Main"
    return None


def event_facts(doc: DocText) -> list[Fact]:
    facts: list[Fact] = []
    seen: set[tuple[Any, ...]] = set()
    for pno, page in enumerate(doc.pages, start=1):
        text = flat(page)
        tentative_from = [m.start() for m in re.finditer(r"tentative schedule|tentative", text, re.I)]
        claimed: list[tuple[int, int]] = []
        for etype, rx, kind in _COMPILED:
            for m in rx.finditer(text):
                if any(a <= m.start() < b for a, b in claimed):
                    continue
                window = text[m.end(): m.end() + 140]
                gap_text = window[:60]
                tent = any(0 <= m.start() - t <= 2500 for t in tentative_from) or bool(TENTATIVE.search(text[max(0, m.start() - 40): m.end() + 80]))
                stage = _stage(m.group(0))
                if kind == RANGE:
                    rng = find_range(window)
                    if not rng or rng[0].start > 60:
                        continue
                    a, b = rng
                    quote = text[m.start(): m.end() + b.end]
                    cert = "tentative" if tent or a.precision == "month" else "official"
                    base = {"precision": a.precision, "certainty": cert}
                    if etype == "application_window":
                        pairs = [("application_start", a), ("application_end", b)]
                        # "Registration and payment of fees: X to Y" states the fee deadline in the same breath.
                        if re.search(r"payment of (?:application )?fee", m.group(0), re.I):
                            pairs.append(("fee_deadline", b))
                    elif etype == "fee_window":
                        pairs = [("fee_deadline", b)]
                    else:
                        facts.append(Fact("event", {"event_type": "correction_window", "date": a.value.isoformat(),
                                                    "date_end": b.value.isoformat(), **base}, quote, pno, 0.85))
                        claimed.append((m.start(), m.end() + b.end))
                        continue
                    for et, d in pairs:
                        key = (et, d.value, stage)
                        if key not in seen:
                            seen.add(key)
                            facts.append(Fact("event", {"event_type": et, "date": d.value.isoformat(), "stage": stage, **base},
                                              quote, pno, 0.9 if d.precision == "day" else 0.7))
                    claimed.append((m.start(), m.end() + b.end))
                else:
                    ds = [d for d in find_dates(window) if d.start <= 60]
                    if not ds:
                        continue
                    d = ds[0]
                    prefix = text[max(0, m.start() - 30): m.start()].lower()
                    # A label mentioned in passing ("within one year from the last date ...") is not a label.
                    if re.search(r"(from|within|before|after|till|until|of|for)\s+(the\s+)?$", prefix):
                        continue
                    if etype == "exam" and re.search(r"(result|call letters?|download)\s*(of|for)?\s*$", prefix):
                        continue
                    gap = gap_text[: d.start]
                    if re.search(r"\bfrom\b", gap, re.I):
                        rng = find_range(window)
                        if etype != "application_end" or not rng:
                            continue
                        d = rng[1]
                    # Reject when another label sits between this label and the date.
                    elif re.search(r"last date|date of|online examination|registration", gap, re.I):
                        continue
                    key = (etype, d.value, stage)
                    if key in seen:
                        continue
                    seen.add(key)
                    quote = text[m.start(): m.end() + d.end]
                    cert = "tentative" if tent or d.precision == "month" else "official"
                    conf = 0.92 if d.start <= 25 and d.precision == "day" else 0.75
                    facts.append(Fact("event", {"event_type": etype, "date": d.value.isoformat(), "stage": stage,
                                                "precision": d.precision, "certainty": cert}, quote, pno, conf))
                    claimed.append((m.start(), m.end() + d.end))
    return facts


RE_AMOUNT = re.compile(r"(?:Rs\.?|₹|INR)\s*([\d,]{2,7})\s*(?:/-)?", re.I)
FEE_CATS = r"(General|Gen\.?|UR|OBC|EWS|SC|ST|PwBD|PWD|Women|Female|Ex-?servicem[ae]n|XS|DXS|Others|All)"


def fee_facts(doc: DocText) -> list[Fact]:
    facts = []
    for pno, page in enumerate(doc.pages, start=1):
        text = flat(page)
        for sec in re.finditer(r"(application )?fee", text, re.I):
            region = text[sec.start(): sec.start() + 700]
            for m in RE_AMOUNT.finditer(region):
                ctx = region[max(0, m.start() - 70): m.start()]
                cats = re.findall(FEE_CATS, ctx, re.I)
                if not cats:
                    continue
                amount = int(m.group(1).replace(",", ""))
                if amount < 10 or amount > 10000:
                    continue
                quote = region[max(0, m.start() - 70): m.end()]
                cat_set = sorted({c.upper() for c in cats})
                value = ({"applies_to": "others", "exempted": cat_set, "amount": amount}
                         if re.search(r"exempt|except", ctx, re.I) else {"categories": cat_set, "amount": amount})
                facts.append(Fact("fee", value, quote.strip(), pno, 0.7))
            if facts:
                return facts
    return facts


RE_VAC = re.compile(r"(?:number of|total(?: no\.? of)?|no\.? of) vacanc(?:y|ies)\s*:?\s*\(?(\d[\d,]{0,6})", re.I)


def vacancy_facts(doc: DocText) -> list[Fact]:
    for pno, page in enumerate(doc.pages, start=1):
        text = flat(page)
        m = RE_VAC.search(text)
        if m:
            return [Fact("vacancies", {"total": int(m.group(1).replace(",", ""))}, m.group(0), pno, 0.85)]
    return []


RE_BORN = re.compile(
    r"born (?:between|not earlier than)\s+(.{3,40}?\d{4})\.?\s*,?\s+and\s+(?:not later than\s+)?(.{3,40}?\d{4})", re.I)
RE_AGE_RANGE = re.compile(
    r"(?:age limit|age)\s*:?\s*(?:\(as on\s+([^)]{6,30})\))?\s*:?\s*(\d{2})\s*(?:-|–|to)\s*(\d{2})(?:\s*years)?", re.I)
RE_UPSC_AGE = re.compile(
    r"attained the age of (\d{2}) years and must not\s+have attained the age of (\d{2}) years on the\s+(.{6,30}?\d{4})", re.I)


def age_facts(doc: DocText) -> list[Fact]:
    for pno, page in enumerate(doc.pages, start=1):
        text = flat(page)
        m = RE_BORN.search(text)
        if not m:
            continue
        d1, d2 = find_dates(m.group(1)), find_dates(m.group(2))
        if not (d1 and d2):
            continue
        value: dict[str, Any] = {"type": "born_between", "from": d1[0].value.isoformat(), "to": d2[0].value.isoformat()}
        start = m.start()
        rng = RE_AGE_RANGE.search(text[max(0, m.start() - 120): m.start()])
        if rng:
            value.update({"min_age": int(rng.group(2)), "max_age": int(rng.group(3))})
            start = max(0, m.start() - 120) + rng.start()
        up = RE_UPSC_AGE.search(text[max(0, m.start() - 300): m.end()])
        if up:
            cut = find_dates(up.group(3))
            value.update({"min_age": int(up.group(1)), "max_age": int(up.group(2))})
            if cut:
                value["cutoff_date"] = cut[0].value.isoformat()
            start = max(0, m.start() - 300) + up.start()
        quote = text[start: m.end()].strip()
        return [Fact("age_rule", value, quote, pno, 0.9)]
    return []


NOTIFICATION_NUMBER = [
    re.compile(r"EXAMINATION NOTICE NO\.?\s*:?\s*([\w/.-]+\d[\w/.-]*)", re.I),
    re.compile(r"ADVERTISEMENT NO\.?\s*:?\s*([A-Z0-9][A-Z0-9/.-]{4,40})", re.I),
    re.compile(r"\bCEN\s*(?:No\.?)?\s*(\d{2}/\d{4})", re.I),
    re.compile(r"\bAdvt\.?\s*No\.?\s*:?\s*([\w/.-]*\d[\w/.-]*)", re.I),
    re.compile(r"CATEGORY\s*No\.?\s*:?\s*(\d{1,3}/\d{4})", re.I),
]


def notification_number_facts(doc: DocText) -> list[Fact]:
    for pno, page in enumerate(doc.pages[:3], start=1):
        text = flat(page)
        for rx in NOTIFICATION_NUMBER:
            m = rx.search(text)
            if m:
                return [Fact("notification_number", {"number": m.group(1).rstrip(".,")}, m.group(0), pno, 0.9)]
    return []


RE_KB = re.compile(r"(\d{1,3})\s*kb\s*(?:to|-|–|and)\s*(\d{1,4})\s*kb", re.I)
RE_PX = re.compile(r"(\d{2,4})\s*(?:x|×|\*)\s*(\d{2,4})\s*pixels?", re.I)


def photo_spec_facts(doc: DocText) -> list[Fact]:
    facts = []
    for pno, page in enumerate(doc.pages, start=1):
        text = flat(page)
        mentions = sorted((m.start(), item) for item in ("photograph", "signature", "thumb impression", "hand-?writ(?:ten|ing) declaration")
                          for m in re.finditer(item, text, re.I))
        for item in ("photograph", "signature", "thumb impression", "hand-?writ(?:ten|ing) declaration"):
            for m in re.finditer(item, text, re.I):
                nxt = min([pos for pos, it in mentions if pos > m.start() and it != item] + [m.start() + 260])
                region = text[m.start(): min(nxt, m.start() + 260)]
                kb, px = RE_KB.search(region), RE_PX.search(region)
                if not kb:
                    continue
                value: dict[str, Any] = {"item": "handwritten declaration" if item.startswith("hand") else item,
                                         "min_kb": int(kb.group(1)), "max_kb": int(kb.group(2)), "formats": ["jpg", "jpeg"]}
                end = kb.end()
                if px:
                    value.update({"width": int(px.group(1)), "height": int(px.group(2))})
                    end = max(end, px.end())
                facts.append(Fact("photo_spec", value, region[:end], pno, 0.8))
                break
        if facts:
            return facts
    return facts


def generic_facts(doc: DocText) -> list[Fact]:
    return (event_facts(doc) + fee_facts(doc) + vacancy_facts(doc) + age_facts(doc)
            + notification_number_facts(doc) + photo_spec_facts(doc) + certificate_facts(doc))


CERT_NAMES = [
    (r"OBC\s*\((?:NCL|Non[- ]Creamy Layer)\)\s*certificate|non[- ]creamy layer certificate|OBC certificate", "OBC (non-creamy layer)"),
    (r"Income\s*&\s*Asset\s*Certificate|EWS certificate|Economically Weaker Section", "EWS (income and asset)"),
    (r"disability certificate", "Disability"),
    (r"(?:caste|community) certificate", "Caste / community"),
    (r"income certificate", "Income"),
]


def _cert_name(text: str) -> str | None:
    best = None
    for rx, name in CERT_NAMES:
        for m in re.finditer(rx, text, re.I):
            if best is None or m.start() > best[0]:
                best = (m.start(), name)
    return best[1] if best else None


def certificate_facts(doc: DocText) -> list[Fact]:
    """Rules on how recent a certificate must be, for on-device validity reminders. Only what the notice states."""
    facts: list[Fact] = []
    seen: set[tuple[Any, ...]] = set()
    for pno, page in enumerate(doc.pages, start=1):
        text = flat(page)
        for m in re.finditer(r"(?:issued|dated) on\s*/\s*after|(?:issued|dated) on or after", text, re.I):
            cert = _cert_name(text[max(0, m.start() - 260): m.start()])
            after = find_dates(text[m.end(): m.end() + 25])
            if not cert or not after:
                continue
            value: dict[str, Any] = {"certificate": cert, "issued_from": after[0].value.isoformat()}
            tail = text[m.end(): m.end() + 260]
            end = m.end() + after[0].end
            lim = re.search(r"(?:not later than|till|but before)\s+(the closing date[^|]{0,140}?|the date of interview|last date of [a-z ]+)", tail, re.I)
            if lim:
                ie = re.search(r"i\.\s?e\.?\s*(\d{2}\.\d{2}\.\d{4})", tail[lim.end(): lim.end() + 40])
                if ie and (d := find_dates(ie.group(1))):
                    value["issued_until"] = d[0].value.isoformat()
                    end = m.end() + lim.end() + ie.end()
                else:
                    value["until_event"] = "interview" if "interview" in lim.group(1).lower() else "application_end"
                    end = m.end() + lim.end()
            fy = re.search(r"Financial Year\s*\(FY\)\s*(\d{4}-\d{2,4})", text[max(0, m.start() - 200): m.start()], re.I)
            if fy:
                value["financial_year"] = fy.group(1)
            key = tuple(sorted(value.items()))
            if key in seen:
                continue
            seen.add(key)
            facts.append(Fact("certificate_rule", value, text[max(0, m.start() - 160): end].strip(), pno, 0.88))
        for m in re.finditer(r"certificate should be dated on or before (?:the )?last date of (?:registration|receipt|submission)", text, re.I):
            cert = _cert_name(text[max(0, m.start() - 300): m.end()])
            if not cert:
                continue
            value = {"certificate": cert, "until_event": "application_end"}
            key = tuple(sorted(value.items()))
            if key not in seen:
                seen.add(key)
                facts.append(Fact("certificate_rule", value, text[max(0, m.start() - 120): m.end()].strip(), pno, 0.88))
        for m in re.finditer(r"(?:EWS|Economically Weaker Section)[^|]{0,120}?certificate should be valid for the year (\d{4}-\d{2,4}) for the financial year (\d{4}-\d{2,4})",
                             text, re.I):
            value = {"certificate": "EWS (income and asset)", "valid_year": m.group(1), "financial_year": m.group(2)}
            key = tuple(sorted(value.items()))
            if key not in seen:
                seen.add(key)
                facts.append(Fact("certificate_rule", value, m.group(0), pno, 0.88))
    return facts
