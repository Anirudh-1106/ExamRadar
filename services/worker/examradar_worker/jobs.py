"""Job bodies shared by Celery tasks and the single-process local runner."""

import logging
from datetime import timedelta

from examradar_core.db import session_scope
from examradar_core.models import ScamCheck, Source
from examradar_core.timeutil import ist_today, utcnow
from sqlalchemy import delete, select

from . import notify
from .pipeline import Pipeline
from .registry_sync import sync_registry

log = logging.getLogger(__name__)


def sync() -> None:
    with session_scope() as s:
        sync_registry(s)


def crawl_source(source_id: int, force: bool = False) -> dict:
    with session_scope() as s:
        src = s.get(Source, source_id)
        p = Pipeline(s, force=force)
        run = p.run_source(src)
        out = {"source": src.key, "status": run.status if run else "skipped", "items": run.items_found if run else 0,
               "new": run.new_items if run else 0, "error": run.error if run else None}
        log.info("crawl finished", extra={"data": out})
        return out


def process_documents(limit: int = 20) -> int:
    with session_scope() as s:
        return Pipeline(s).process_documents(limit)


def due_source_ids() -> list[int]:
    with session_scope() as s:
        return [src.id for src in Pipeline(s).due_sources()]


def reminders() -> int:
    with session_scope() as s:
        return notify.deadline_reminders(s, ist_today())


def dispatch() -> int:
    with session_scope() as s:
        return notify.dispatch(s)


def health() -> int:
    with session_scope() as s:
        return Pipeline(s).check_health()


def purge_scam_text() -> int:
    """Submitted text is not kept beyond the retention window; verdicts and evidence summaries remain."""
    with session_scope() as s:
        rows = s.scalars(select(ScamCheck).where(ScamCheck.purge_after < utcnow(), ScamCheck.submitted_text.is_not(None))).all()
        for r in rows:
            r.submitted_text = None
        old = utcnow() - timedelta(days=90)
        s.execute(delete(ScamCheck).where(ScamCheck.created_at < old))
        return len(rows)


def tick() -> dict:
    """One scheduler step: crawl what is due, then process documents and deliver notifications."""
    results = [crawl_source(i) for i in due_source_ids()]
    docs = process_documents()
    sent = dispatch()
    return {"crawled": results, "documents": docs, "dispatched": sent}


def reprocess(org_key: str) -> dict:
    """Re-read every stored document of one organisation with the current rules and OCR.

    Facts that already match are confirmed; new or changed ones go through the normal validation and review path.
    Review tasks raised only because a scan was unreadable are closed once the text reads well.
    """
    from examradar_adapters.base import CycleHint, Item
    from examradar_core.models import Document, ExamCycle, Organisation, ReviewTask, SourceItem
    from examradar_core.storage import get_store

    done = facts = 0
    with session_scope() as s:
        p = Pipeline(s)
        org = s.scalar(select(Organisation).where(Organisation.key == org_key))
        ad = p.adapter(org_key)
        src_ids = [x.id for x in org.sources]
        for si in s.scalars(select(SourceItem).where(SourceItem.source_id.in_(src_ids), SourceItem.document_id.is_not(None))).all():
            d = s.get(Document, si.document_id)
            payload = si.data or {}
            item = Item(key=si.item_key, title=si.title, url=si.url, kind=si.kind, doc_urls=payload.get("doc_urls", []),
                        cycle=CycleHint(**payload["cycle"]) if payload.get("cycle") else None, published_hint=si.published_hint)
            cycle = s.get(ExamCycle, si.exam_cycle_id) if si.exam_cycle_id else None
            facts += len(p.process_document(org, ad, item, cycle, d, get_store().get(d.storage_key)))
            done += 1
            if (d.text_quality or 0) >= 0.5:
                for t in s.scalars(select(ReviewTask).where(ReviewTask.status == "open", ReviewTask.reason.like(f"Low text quality%{d.url}%"))):
                    t.status, t.resolved_by, t.resolved_at, t.resolution = "approved", "ocr", utcnow(), {"note": "re-read with OCR"}
    return {"organisation": org_key, "documents": done, "facts": facts}
