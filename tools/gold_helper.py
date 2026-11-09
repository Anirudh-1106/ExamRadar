"""Helper for labelling gold documents. Independent of the extraction rules: it shows raw text around key phrases
and proposes values with plain strptime parsing, for a human (or reviewer) to check line by line.

Usage: python tools/gold_helper.py kerala_psc 150 > review.txt
Outputs, per document: URL, SHA-256, raw snippets, and a proposed label as one JSON line prefixed with 'LABEL '.
"""

import json
import re
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

from examradar_core.db import session_scope  # noqa: E402
from examradar_core.models import Document  # noqa: E402
from sqlalchemy import select  # noqa: E402


def to_iso(raw: str) -> str | None:
    raw = re.sub(r"\s", "", raw).replace("-", ".").replace("/", ".")
    for fmt in ("%d.%m.%Y",):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def snippet(t: str, pattern: str, width: int = 170) -> str | None:
    m = re.search(pattern, t, re.I)
    return t[m.start(): m.start() + width] if m else None


def main() -> None:
    org, limit = sys.argv[1], int(sys.argv[2])
    with session_scope() as s:
        q = select(Document).where(Document.url.like("%keralapsc.gov.in/sites/default/files/%noti-%"), Document.text.is_not(None))
        if org != "kerala_psc":
            raise SystemExit("only kerala_psc notifications are supported by this helper")
        for d in s.scalars(q.order_by(Document.url)).all()[:limit]:
            t = " ".join((d.text or "").split())
            cat = snippet(t, r"CATEGORY\s*No\.?", 40)
            last = snippet(t, r"Last date for (?:receipt|submission)", 120)
            born = snippet(t, r"born between", 90)
            vac = snippet(t, r"Number of Vacanc", 60)
            label: dict = {"url": d.url, "sha256": d.sha256}
            # Some PDFs space out the digits ("3 61 /2025"); join them and keep the value only if it is a plausible number.
            if cat and (m := re.search(r"No\.?\s*:?\s*([\d ]{1,8})/\s*(\d{4})", cat, re.I)):
                digits = m.group(1).replace(" ", "")
                if 0 < len(digits) <= 3:
                    label["notification_number"] = f"{int(digits):03d}/{m.group(2)}"
            if last and (m := re.search(r"(\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{4})", last)):
                label["application_end"] = to_iso(m.group(1))
            if born and len(ms := re.findall(r"(\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{4})", born)) >= 2:
                label["age"] = {"from": to_iso(ms[0]), "to": to_iso(ms[1])}
            if vac and (m := re.search(r":\s*(\d{1,4})\s*\(", vac)):
                label["vacancies"] = int(m.group(1))
            print(f"### {d.url.rsplit('/', 1)[-1]}")
            for name, sn in (("CAT", cat), ("LAST", last), ("BORN", born), ("VAC", vac)):
                print(f"  {name}: {sn}")
            print("LABEL " + json.dumps(label, ensure_ascii=False))


if __name__ == "__main__":
    main()
