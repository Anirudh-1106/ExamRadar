"""Operations performed by admins. Every function writes an audit log entry."""

from datetime import date
from typing import Any

from examradar_core.models import (
    AuditLog,
    Document,
    Event,
    EventRevision,
    Exam,
    ExamCycle,
    ExtractedField,
    FieldEvidence,
    Organisation,
    ReviewTask,
)
from examradar_core.timeutil import utcnow
from examradar_extraction.validate import link_allowed
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import notify
from .pipeline import Pipeline


class OpError(ValueError):
    pass


def audit(s: Session, actor: str, action: str, entity: str, entity_id: int | None, before=None, after=None, ip=None) -> None:
    s.add(AuditLog(actor=actor, action=action, entity=entity, entity_id=entity_id, before=before, after=after, ip=ip))


def approve_task(s: Session, task_id: int, actor: str, edited_value: dict[str, Any] | None = None, ip: str | None = None) -> None:
    t = s.get(ReviewTask, task_id)
    if t is None or t.status != "open":
        raise OpError("task is not open")
    p = Pipeline(s, notify_enabled=True)
    if t.extracted_field_id:
        ef = s.get(ExtractedField, t.extracted_field_id)
        ev = s.scalar(select(FieldEvidence).where(FieldEvidence.extracted_field_id == ef.id))
        cycle = s.get(ExamCycle, t.exam_cycle_id or ef.exam_cycle_id)
        if cycle is None:
            raise OpError("no exam cycle attached; use manual entry")
        org = s.get(Organisation, cycle.exam.organisation_id)
        value = {**ef.value, **(edited_value or {})}
        doc = s.get(Document, ef.document_id)
        if t.kind == "revision" and t.payload and t.payload.get("event_id"):
            e = s.get(Event, t.payload["event_id"])
            new = {**t.payload["new"], **(edited_value or {})}
            p.publish_event(cycle, e.event_type, e.label, e.category_number, date.fromisoformat(new["date"]),
                            date.fromisoformat(new["date_end"]) if new.get("date_end") else None, new.get("precision", "day"),
                            new.get("certainty", "official"), ev, doc, e, "Changed in the official source (reviewed)", actor)
            ef.status = "published"
        else:
            p.apply_one(org, cycle, (value.get("category_numbers") or [None])[0], ef.field_name, value, ef, ev, doc,
                        "manual", 1.0, force=True, actor=actor, reason="Reviewed and approved")
        if edited_value:
            ef.value = value
    t.status = "edited" if edited_value else "approved"
    t.resolved_at, t.resolved_by, t.resolution = utcnow(), actor, {"edited": edited_value}
    audit(s, actor, "review.approve", "review_task", t.id, after={"edited": edited_value}, ip=ip)
    s.flush()


def reject_task(s: Session, task_id: int, actor: str, reason: str, ip: str | None = None) -> None:
    t = s.get(ReviewTask, task_id)
    if t is None or t.status != "open":
        raise OpError("task is not open")
    if t.extracted_field_id:
        s.get(ExtractedField, t.extracted_field_id).status = "rejected"
    t.status, t.resolved_at, t.resolved_by, t.resolution = "rejected", utcnow(), actor, {"reason": reason}
    audit(s, actor, "review.reject", "review_task", t.id, after={"reason": reason}, ip=ip)
    s.flush()


def manual_event(s: Session, actor: str, *, cycle_id: int | None, org_key: str, exam_name: str | None, cycle_title: str | None,
                 event_type: str, date_start: date, date_end: date | None, certainty: str, source_url: str, quote: str,
                 precision: str = "day", ip: str | None = None) -> Event:
    """Manual entry still needs an official source: the URL must be on the organisation's allowlist."""
    org = s.scalar(select(Organisation).where(Organisation.key == org_key))
    if org is None:
        raise OpError("unknown organisation")
    p = Pipeline(s)
    if not link_allowed(source_url, p.domains(org.id)):
        raise OpError("source URL is not an allowlisted official address for this organisation")
    if not quote.strip():
        raise OpError("a supporting quote from the official source is required")
    if certainty not in ("official", "tentative"):
        raise OpError("manual entries must be official or tentative")
    if cycle_id:
        cycle = s.get(ExamCycle, cycle_id)
    else:
        if not (exam_name and cycle_title):
            raise OpError("exam name and cycle title are required")
        from examradar_adapters.base import CycleHint, slugify

        cycle = p.cycle_from_hint(org, CycleHint(f"{org.key}-{slugify(exam_name)}", exam_name, cycle_title,
                                                 s.scalar(select(Exam.sector).where(Exam.organisation_id == org.id)) or "other"),
                                  source_url)
    ev = FieldEvidence(source_url=source_url, quote=quote[:4000])
    s.add(ev)
    s.flush()
    existing = s.scalar(select(Event).where(Event.exam_cycle_id == cycle.id, Event.event_type == event_type,
                                            Event.status == "active", Event.category_number.is_(None)))
    e = p.publish_event(cycle, event_type, None, None, date_start, date_end, precision, certainty, ev, None, existing,
                        "Entered by admin from the official source", actor)
    if not cycle.official_url:
        cycle.official_url = source_url
    audit(s, actor, "manual.event", "event", e.id, after={"type": event_type, "date": date_start.isoformat(), "source": source_url}, ip=ip)
    s.flush()
    return e


def retract_event(s: Session, event_id: int, actor: str, reason: str, ip: str | None = None) -> EventRevision:
    """Emergency control: withdraw an incorrect update and send a correction to everyone who could have seen it."""
    e = s.get(Event, event_id)
    if e is None or e.status != "active":
        raise OpError("event is not active")
    old = {"date_start": e.date_start.isoformat() if e.date_start else None, "certainty": e.certainty}
    e.status, e.revision_count = "retracted", e.revision_count + 1
    rev = EventRevision(event_id=e.id, revision_no=e.revision_count, kind="retract", old_value=old, new_value=None,
                        reason=reason, created_by=actor)
    s.add(rev)
    s.flush()
    notify.on_event_published(s, e, rev)
    audit(s, actor, "event.retract", "event", e.id, before=old, after={"reason": reason}, ip=ip)
    s.flush()
    return rev


def retract_cycle(s: Session, cycle_id: int, actor: str, reason: str, ip: str | None = None) -> None:
    c = s.get(ExamCycle, cycle_id)
    if c is None:
        raise OpError("unknown exam")
    c.retracted = True
    for e in s.scalars(select(Event).where(Event.exam_cycle_id == c.id, Event.status == "active")):
        retract_event(s, e.id, actor, reason, ip)
    audit(s, actor, "cycle.retract", "exam_cycle", c.id, after={"reason": reason}, ip=ip)
