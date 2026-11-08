"""Indian date formats. Numeric dates are always day-month-year; US order is never assumed."""

import re
from dataclasses import dataclass
from datetime import date

EN_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}
ML_MONTHS = {
    "ജനുവരി": 1, "ഫെബ്രുവരി": 2, "മാർച്ച്": 3, "ഏപ്രിൽ": 4, "മേയ്": 5, "മെയ്": 5, "ജൂൺ": 6,
    "ജൂലൈ": 7, "ആഗസ്റ്റ്": 8, "ഓഗസ്റ്റ്": 8, "സെപ്റ്റംബർ": 9, "ഒക്ടോബർ": 10, "നവംബർ": 11, "ഡിസംബർ": 12,
}

_MON = "|".join(sorted(EN_MONTHS, key=len, reverse=True))
_ML = "|".join(sorted(ML_MONTHS, key=len, reverse=True))

RE_NUM = re.compile(r"(?<![\d/.-])(\d{1,2})\s?[./-]\s?(\d{1,2})\s?[./-]\s?(\d{4}|\d{2})(?![\d/])")
# OCR often turns a superscript ordinal ("9th") into a quote or degree mark: 09" November 2026.
RE_DMY = re.compile(rf"(?<!\d)(\d{{1,2}})(?:st|nd|rd|th|[\"'”’°ºª])?\s*(?:of\s+)?[-\s]?({_MON})\.?[-,\s]+(\d{{4}})", re.I)
RE_MDY = re.compile(rf"\b({_MON})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})", re.I)
RE_MY = re.compile(rf"\b({_MON})\.?,?\s+(\d{{4}})\b", re.I)
RE_ML = re.compile(rf"(\d{{4}})\s*({_ML})\s*(?:മാസം)?\s*(\d{{1,2}})")


@dataclass(frozen=True)
class FoundDate:
    value: date
    precision: str  # day | month
    start: int
    end: int
    raw: str


def _mk(y: int, m: int, d: int) -> date | None:
    if y < 100:
        y += 2000
    try:
        return date(y, m, d)
    except ValueError:
        return None


def find_dates(text: str) -> list[FoundDate]:
    found: list[FoundDate] = []
    taken: list[tuple[int, int]] = []

    def free(s: int, e: int) -> bool:
        return all(e <= a or s >= b for a, b in taken)

    def add(v: date | None, prec: str, m: re.Match[str]) -> None:
        if v and free(m.start(), m.end()):
            found.append(FoundDate(v, prec, m.start(), m.end(), m.group(0)))
            taken.append((m.start(), m.end()))

    for m in RE_DMY.finditer(text):
        add(_mk(int(m.group(3)), EN_MONTHS[m.group(2).lower()], int(m.group(1))), "day", m)
    for m in RE_MDY.finditer(text):
        add(_mk(int(m.group(3)), EN_MONTHS[m.group(1).lower()], int(m.group(2))), "day", m)
    for m in RE_NUM.finditer(text):
        add(_mk(int(m.group(3)), int(m.group(2)), int(m.group(1))), "day", m)
    for m in RE_ML.finditer(text):
        add(_mk(int(m.group(1)), ML_MONTHS[m.group(2)], int(m.group(3))), "day", m)
    for m in RE_MY.finditer(text):
        if m.group(1).lower() == "may" and not re.match(r"May,?\s+\d{4}", m.group(0)):
            continue
        add(_mk(int(m.group(2)), EN_MONTHS[m.group(1).lower()], 1), "month", m)
    return sorted(found, key=lambda f: f.start)


def parse_date(text: str) -> FoundDate | None:
    ds = find_dates(text)
    return ds[0] if ds else None


RE_RANGE_SEP = re.compile(r"^\s*(?:to|till|until|upto|up to|–|—|-|and)\s*$", re.I)


def find_range(text: str) -> tuple[FoundDate, FoundDate] | None:
    """First pair of dates joined by 'to', 'till', or a dash."""
    ds = find_dates(text)
    for a, b in zip(ds, ds[1:], strict=False):
        if RE_RANGE_SEP.match(text[a.end:b.start]) and a.value <= b.value:
            return a, b
    return None
