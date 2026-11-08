"""Mirror config/sources.yaml into the database. Idempotent; safe to run on every start."""

from datetime import date

from examradar_adapters.registry import load_config
from examradar_core.models import OfficialDomain, Organisation, Source
from sqlalchemy import select
from sqlalchemy.orm import Session


def _as_date(v) -> date | None:
    if isinstance(v, date):
        return v
    return date.fromisoformat(v) if v else None


def sync_registry(s: Session, path: str | None = None) -> None:
    cfg = load_config(path)
    for o in cfg["organisations"]:
        org = s.scalar(select(Organisation).where(Organisation.key == o["key"]))
        if org is None:
            org = Organisation(key=o["key"], name=o["name"], group=o["group"])
            s.add(org)
            s.flush()
        org.name, org.group, org.collection = o["name"], o["group"], o.get("collection", "auto")
        existing = {(d.host, d.path_prefix, d.purpose): d for d in org.domains}
        for d in o.get("domains", []):
            k = (d["host"], d.get("path_prefix", "/"), d["purpose"])
            if k not in existing:
                s.add(OfficialDomain(organisation_id=org.id, host=d["host"], path_prefix=d.get("path_prefix", "/"),
                                     purpose=d["purpose"], verified_at=_as_date(d.get("verified")),
                                     verified_by="source recon", note=d.get("note")))
        sched = o.get("schedule", {})
        for entry in o.get("listings", []):
            url = entry if isinstance(entry, str) else entry["url"]
            kind = "listing" if isinstance(entry, str) else entry.get("kind", "listing")
            key = f"{o['key']}:{url}"
            src = s.scalar(select(Source).where(Source.key == key))
            if src is None:
                src = Source(key=key, organisation_id=org.id, adapter=o["key"], url=url, kind=kind)
                s.add(src)
            src.every_minutes = sched.get("every_minutes", 120)
            src.active_deadline_minutes = sched.get("active_deadline_minutes")
            src.enabled = o.get("collection", "auto") != "manual"
        if o.get("collection") in ("manual", "rss_and_manual"):
            key = f"{o['key']}:manual"
            if s.scalar(select(Source).where(Source.key == key)) is None:
                s.add(Source(key=key, organisation_id=org.id, adapter=o["key"], url=o.get("apply_entry") or "",
                             kind="manual", enabled=False, status="manual"))
    for f in cfg.get("news_feeds", []):
        key = f["key"]
        src = s.scalar(select(Source).where(Source.key == key))
        if src is None:
            src = Source(key=key, adapter="news", url=f["url"], kind="news", is_official=False)
            s.add(src)
        src.enabled = bool(f.get("enabled", True))
        src.every_minutes = f.get("every_minutes", 60)
        src.status = src.status if src.enabled else "disabled"
    s.flush()
