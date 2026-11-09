"""Field-level precision and recall of the rule extractors against data/gold/labels.yaml.

Usage: python tools/evaluate.py   (prints a table and writes docs/evaluation-results.md)

Bulk labels (data/gold/bulk-*.yaml) name documents by URL and SHA-256. They are read from local object storage, or
downloaded once into data/gold/cache, and the hash is checked before scoring.
"""

import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from examradar_adapters.base import Item, Listing  # noqa: E402
from examradar_adapters.registry import build_adapter, organisations  # noqa: E402
from examradar_core.settings import get_settings  # noqa: E402
from examradar_core.storage import content_key, sha256  # noqa: E402
from examradar_extraction.pdf import extract_pdf  # noqa: E402
from examradar_extraction.validate import verify_quote  # noqa: E402

FIX = ROOT / "data" / "fixtures"
CACHE = ROOT / "data" / "gold" / "cache"


def load_by_hash(url: str, digest: str) -> bytes | None:
    """Stored copy first, then the cache, then one polite download. Returns None if the bytes do not match."""
    for path in (Path(get_settings().local_storage_dir) / content_key(digest, ".pdf"), CACHE / f"{digest}.pdf"):
        if path.exists():
            data = path.read_bytes()
            if sha256(data) == digest:
                return data
    import httpx

    try:
        data = httpx.get(url, timeout=60, headers={"User-Agent": "ExamRadar-evaluation"}).content
    except httpx.HTTPError:
        return None
    if sha256(data) != digest:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / f"{digest}.pdf").write_bytes(data)
    return data


def d(v) -> str:
    return v.isoformat() if isinstance(v, date) else str(v)


def main() -> None:
    gold = yaml.safe_load((ROOT / "data" / "gold" / "labels.yaml").read_text(encoding="utf-8"))
    orgs = {o["key"]: o for o in organisations()}
    stats: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0])  # tp, fp, fn
    quote_fail = 0
    total_facts = 0

    def score(src: str, field: str, expected: set, got: set) -> None:
        s = stats[(src, field)]
        s[0] += len(expected & got)
        s[1] += len(got - expected)
        s[2] += len(expected - got)

    for g in gold["documents"]:
        ad = build_adapter(orgs[g["source"]])
        item = Item(key=g["file"], title=g.get("title", g["file"]), url=None, kind=g["kind"])
        doc = extract_pdf((FIX / g["file"]).read_bytes(), **ad.doc_options(item))
        facts = ad.extract(item, doc)
        total_facts += len(facts)
        quote_fail += sum(1 for f in facts if not verify_quote(f.quote, doc.pages).ok)
        src = g["source"]
        if "events" in g:
            scope = set(g.get("scored_categories", []))
            exp = {(e[0], e[1], d(e[2]), e[3], e[4]) for e in g["events"]}
            got = set()
            for f in facts:
                if f.field != "event":
                    continue
                cats = f.value.get("category_numbers") or [None]
                for c in cats:
                    if scope and c not in scope:
                        continue
                    got.add((f.value["event_type"], f.value.get("stage"), f.value["date"], f.value.get("precision", "day"), c))
            score(src, "dates", exp, got)
        if "calendar_events" in g:
            exp = {(e[0], e[1], e[2], d(e[3])) for e in g["calendar_events"]}
            titles = {e[0] for e in g["calendar_events"]}
            got = {(f.value["cycle"]["title"], f.value["event_type"], f.value.get("stage"), f.value["date"])
                   for f in facts if f.field == "event" and f.value["cycle"]["title"] in titles}
            score(src, "calendar dates", exp, got)
        if "age" in g:
            exp = {(d(g["age"]["from"]), d(g["age"]["to"]))}
            got = {(f.value.get("from"), f.value.get("to")) for f in facts if f.field == "age_rule"}
            score(src, "age limit", exp, got)
        if "notification_number" in g:
            score(src, "notification number", {g["notification_number"]},
                  {f.value["number"] for f in facts if f.field == "notification_number"})
        if "vacancies" in g:
            score(src, "vacancies", {g["vacancies"]}, {f.value["total"] for f in facts if f.field == "vacancies"})
        if "certificates" in g:
            exp = {(c["certificate"], d(c.get("issued_from", "")), c.get("valid_year", "")) for c in g["certificates"]}
            got = {(f.value["certificate"], f.value.get("issued_from", ""), f.value.get("valid_year", "")) for f in facts
                   if f.field == "certificate_rule"}
            score(src, "certificate rules", exp, got)
        if "photo_specs" in g:
            exp = {(s["item"], s["min_kb"], s["max_kb"], s.get("width"), s.get("height")) for s in g["photo_specs"]}
            got = {(f.value["item"], f.value["min_kb"], f.value["max_kb"], f.value.get("width"), f.value.get("height"))
                   for f in facts if f.field == "photo_spec"}
            score(src, "photo spec", exp, got)

    # Bulk documents: one labelled value per field, scored as found / wrong / missed.
    bulk_docs = unavailable = 0
    for bulk in sorted((ROOT / "data" / "gold").glob("bulk-*.yaml")):
        spec = yaml.safe_load(bulk.read_text(encoding="utf-8"))
        src = spec.get("source", "kerala_psc")
        ad = build_adapter(orgs[src])
        for g in spec["documents"]:
            data = load_by_hash(g["url"], g["sha256"])
            if data is None:
                unavailable += 1
                continue
            bulk_docs += 1
            item = Item(key=g["url"], title=g["url"].rsplit("/", 1)[-1], url=g["url"], kind=spec.get("kind", "notification"))
            doc = extract_pdf(data, **ad.doc_options(item))
            facts = ad.extract(item, doc)
            total_facts += len(facts)
            quote_fail += sum(1 for f in facts if not verify_quote(f.quote, doc.pages).ok)
            got_by_field = {
                "notification number": {f.value["number"] for f in facts if f.field == "notification_number"},
                "application end": {f.value["date"] for f in facts if f.field == "event" and f.value["event_type"] == "application_end"},
                "age limit": {(f.value.get("from"), f.value.get("to")) for f in facts if f.field == "age_rule"},
                "vacancies": {f.value["total"] for f in facts if f.field == "vacancies"},
            }
            expected = {
                "notification number": g.get("notification_number"),
                "application end": d(g["application_end"]) if "application_end" in g else None,
                "age limit": (d(g["age"]["from"]), d(g["age"]["to"])) if "age" in g else None,
                "vacancies": g.get("vacancies"),
            }
            for field, want in expected.items():
                if want is None:
                    continue
                st = stats[(src + " (bulk)", field)]
                got = got_by_field[field]
                if want in got:
                    st[0] += 1
                elif got:
                    st[1] += 1
                    st[2] += 1
                else:
                    st[2] += 1

    for g in gold["listings"]:
        ad = build_adapter(orgs[g["source"]])
        items = ad.parse_listing(Listing(g["url"]), (FIX / g["file"]).read_bytes(), g["url"])
        keys = {e[0] for e in g["item_events"]}
        exp = {(e[0], e[1], d(e[2])) for e in g["item_events"]}
        got = set()
        for it in items:
            label = next((k for k in keys if k in it.title or k == it.data.get("advertisement")), None)
            if label is None:
                continue
            for f in it.facts:
                if f.field == "event":
                    got.add((label, f.value["event_type"], f.value["date"]))
                    total_facts += 1
        score(g["source"], "listing dates", exp, got)

    rows = []
    tot = [0, 0, 0]
    for (src, field), (tp, fp, fn) in sorted(stats.items()):
        p = tp / (tp + fp) if tp + fp else None
        r = tp / (tp + fn) if tp + fn else None
        rows.append((src, field, tp, fp, fn, p, r))
        tot = [tot[0] + tp, tot[1] + fp, tot[2] + fn]
    fmt = lambda x: "n/a" if x is None else f"{x:.1%}"  # noqa: E731
    lines = ["| Source | Field | Correct | Wrong | Missed | Precision | Recall |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {s} | {f} | {tp} | {fp} | {fn} | {fmt(p)} | {fmt(r)} |" for s, f, tp, fp, fn, p, r in rows]
    tp, fp, fn = tot
    lines.append(f"| **All** | | {tp} | {fp} | {fn} | {fmt(tp / (tp + fp) if tp + fp else None)} | {fmt(tp / (tp + fn) if tp + fn else None)} |")
    out = "\n".join(lines)
    print(out)
    docs_line = (f"Documents scored: {len(gold['documents']) + len(gold['listings']) + bulk_docs} "
                 f"({bulk_docs} bulk; {unavailable} bulk documents unavailable or changed).")
    print(f"\n{docs_line} Extracted facts: {total_facts}. Facts whose quote was not found in the document: {quote_fail}.")
    (ROOT / "docs" / "evaluation-results.md").write_text(
        "# Evaluation results (generated)\n\nGenerated by `python tools/evaluate.py` from `data/gold/labels.yaml`. "
        "These are rule-extractor results before validation and review.\n\n" + out +
        f"\n\n{docs_line} Extracted facts scored: {total_facts}. Facts whose supporting quote failed verification: {quote_fail}.\n",
        encoding="utf-8")


if __name__ == "__main__":
    main()
