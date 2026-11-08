"""Builds API responses from the database. Dates, numbers, and links always come from structured fields."""

from datetime import date
from typing import Any

from examradar_adapters.registry import load_config
from examradar_core.enums import DEADLINE_EVENTS, EVENT_TYPES
from examradar_core.models import (
    CategoryNumber,
    EligibilityRule,
    Event,
    EventRevision,
    Exam,
    ExamCategoryLink,
    ExamCycle,
    ExtractedField,
    FieldEvidence,
    Link,
    NewsItem,
    Organisation,
    Post,
    Source,
    UserChecklistItem,
)
from examradar_core.settings import get_settings
from examradar_eligibility import Profile, RuleSpec, countdown, evaluate
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import schemas as S

DISCLAIMER = ("ExamRadar is independent and is not affiliated with any government body. Information is collected from "
              "official sources and may contain errors. Always confirm details on the linked official website before acting.")


def org_out(o: Organisation) -> S.OrgOut:
    return S.OrgOut(key=o.key, name=o.name, group=o.group, collection=o.collection)


def evidence_out(s: Session, evidence_id: int | None) -> S.EvidenceOut | None:
    if not evidence_id:
        return None
    ev = s.get(FieldEvidence, evidence_id)
    if ev is None:
        return None
    return S.EvidenceOut(quote=ev.quote, page=ev.page, source_url=ev.source_url, document_hash=ev.document_hash,
                         retrieved_at=ev.retrieved_at, published_on=ev.published_on)


def event_title(e: Event) -> str:
    return e.label or EVENT_TYPES.get(e.event_type, e.event_type.replace("_", " ").title())


def event_out(s: Session, e: Event, with_evidence: bool = True) -> S.EventOut:
    return S.EventOut(id=e.id, event_type=e.event_type, title=event_title(e), label=e.label, date_start=e.date_start,
                      date_end=e.date_end, precision=e.precision, certainty=e.certainty, status=e.status,
                      category_number=e.category_number, revision_count=e.revision_count,
                      is_deadline=e.event_type in DEADLINE_EVENTS,
                      evidence=evidence_out(s, e.evidence_id) if with_evidence else None)


def cycle_status(events: list[Event], today: date) -> str:
    act = [e for e in events if e.status == "active" and e.date_start]
    if any(e.event_type == "cancellation" for e in act):
        return "cancelled"

    def first(t: str) -> Event | None:
        xs = sorted([e for e in act if e.event_type == t], key=lambda e: e.date_start)
        return xs[0] if xs else None

    start, end = first("application_start"), first("application_end")
    if end and end.date_start >= today and (start is None or start.date_start <= today):
        return "open"
    if start and start.date_start > today:
        return "upcoming"
    exams = [e for e in act if e.event_type == "exam" and e.precision == "day"]
    if any(e.event_type in ("result", "ranked_list", "short_list") for e in act) and not any(e.date_start >= today for e in exams):
        return "result"
    if any(e.date_start >= today for e in exams):
        return "exam_scheduled"
    if end and end.date_start < today:
        return "closed"
    return "notice"


def _events(s: Session, cycle_id: int) -> list[Event]:
    return list(s.scalars(select(Event).where(Event.exam_cycle_id == cycle_id).order_by(Event.date_start)))


def summary(s: Session, c: ExamCycle, today: date, events: list[Event] | None = None) -> S.ExamSummary:
    events = events if events is not None else _events(s, c.id)
    act = [e for e in events if e.status == "active" and e.date_start]
    upcoming = sorted([e for e in act if (e.date_end or e.date_start) >= today], key=lambda e: e.date_start)
    nxt = next((e for e in upcoming if e.event_type in DEADLINE_EVENTS), upcoming[0] if upcoming else None)
    app_end = next((e for e in sorted(act, key=lambda e: e.date_start, reverse=True) if e.event_type == "application_end"), None)
    exam = next((e for e in sorted(act, key=lambda e: e.date_start) if e.event_type == "exam" and e.date_start >= today), None)
    cats = list(s.scalars(select(CategoryNumber.number).where(CategoryNumber.exam_cycle_id == c.id)))
    org = c.exam.organisation
    return S.ExamSummary(
        id=c.id, title=c.title, exam_name=c.exam.name, organisation=org_out(org), sector=c.exam.sector,
        status=cycle_status(events, today), is_fast_alert=c.is_fast_alert and not act,
        next_event=event_out(s, nxt, False) if nxt else None, application_end=event_out(s, app_end, False) if app_end else None,
        exam_date=event_out(s, exam, False) if exam else None, category_numbers=sorted(cats),
        vacancies_total=c.vacancies_total, has_changes=any(e.revision_count > 1 or e.status == "retracted" for e in events),
        official_url=c.official_url, last_checked_at=c.last_checked_at, updated_at=c.updated_at)


def apply_link(s: Session, c: ExamCycle) -> S.ApplyOut | None:
    org = c.exam.organisation
    link = s.scalar(select(Link).where(Link.exam_cycle_id == c.id, Link.kind == "apply", Link.allowlisted.is_(True)).order_by(Link.id.desc()))
    cfg = next((o for o in load_config()["organisations"] if o["key"] == org.key), {})
    cats = sorted(s.scalars(select(CategoryNumber.number).where(CategoryNumber.exam_cycle_id == c.id)))
    copy_text = cats[0] if cats else c.notification_number
    if link:
        return S.ApplyOut(url=link.url, host=link.host, note="Official application page.", copy_text=copy_text,
                          copy_label="Category number" if cats else ("Notification number" if copy_text else None))
    entry = cfg.get("apply_entry")
    if not entry:
        return None
    host = entry.split("/")[2]
    if org.key == "kerala_psc":
        note = "Thulasi has no direct link for each post. Log in, open Notifications, and search for the category number."
    elif org.key == "rbi":
        note = "RBI's recruitment site may show a security check. Open it in your browser."
    else:
        note = "Official application portal."
    return S.ApplyOut(url=entry, host=host, note=note, copy_text=copy_text,
                      copy_label="Category number" if cats else ("Notification number" if copy_text else None))


def detail(s: Session, c: ExamCycle, today: date) -> S.ExamDetail:
    events = _events(s, c.id)
    base = summary(s, c, today, events)
    posts = []
    for p in s.scalars(select(Post).where(Post.exam_cycle_id == c.id)):
        rules = [S.RuleOut(rule_type=r.rule_type, params=r.params, clause=r.clause_text, evidence=evidence_out(s, r.evidence_id))
                 for r in s.scalars(select(EligibilityRule).where(EligibilityRule.post_id == p.id, EligibilityRule.status == "published"))]
        cat = s.get(CategoryNumber, p.category_number_id).number if p.category_number_id else None
        posts.append(S.PostOut(id=p.id, name=p.name, department=p.department, vacancies=p.vacancies, vacancies_text=p.vacancies_text,
                               pay_scale=p.pay_scale, category_number=cat, rules=rules))
    links = [S.LinkOut(kind=lk.kind, url=lk.url, label=lk.label, host=lk.host)
             for lk in s.scalars(select(Link).where(Link.exam_cycle_id == c.id, Link.allowlisted.is_(True)))]
    pdf = next((lk.url for lk in links if lk.url.lower().split("?")[0].endswith(".pdf") and lk.kind == "notification"), None)
    pub_fields = list(s.scalars(select(ExtractedField).where(ExtractedField.exam_cycle_id == c.id, ExtractedField.status == "published")))
    confirmation = sorted({f.value.get("text", "") for f in pub_fields if f.field_name == "confirmation_note"} - {""})
    specs = [photo_spec(s, f) for f in pub_fields if f.field_name == "photo_spec"]
    fees = [S.FeeOut(amount=f["amount"], categories=f.get("categories", []), applies_to=f.get("applies_to"), exempted=f.get("exempted", []))
            for f in (c.fee_summary or [])]
    combined = []
    for link in s.scalars(select(ExamCategoryLink).where(ExamCategoryLink.exam_cycle_id == c.id)):
        cn = s.get(CategoryNumber, link.category_number_id)
        if cn:
            combined.append(cn.number)
    revs = s.scalars(select(EventRevision).join(Event).where(Event.exam_cycle_id == c.id, EventRevision.revision_no > 1)
                     .order_by(EventRevision.created_at.desc())).all()
    changes = [S.ChangeOut(event_id=r.event_id, event_title=event_title(s.get(Event, r.event_id)), revision_no=r.revision_no,
                           kind=r.kind, old_value=r.old_value, new_value=r.new_value, reason=r.reason, source_url=r.source_url,
                           created_at=r.created_at) for r in revs]
    news = [news_out(n) for n in s.scalars(select(NewsItem).where(NewsItem.matched_exam_cycle_id == c.id, NewsItem.public.is_(True))
                                            .order_by(NewsItem.published_at.desc()).limit(5))] if get_settings().news_mentions_public else []
    org_sources = list(s.scalars(select(Source).where(Source.organisation_id == c.exam.organisation_id, Source.is_official.is_(True))))
    statuses = {x.status for x in org_sources}
    src_status = "blocked" if statuses == {"blocked"} else ("stale" if "stale" in statuses or "failing" in statuses else
                                                          ("manual" if statuses <= {"manual", "disabled"} else "ok"))
    return S.ExamDetail(**base.model_dump(), events=[event_out(s, e) for e in events], posts=posts, links=links,
                        apply=apply_link(s, c), notification_pdf=pdf, fees=fees, qualification_text=c.qualification_text,
                        confirmation_notes=confirmation, photo_specs=specs, combined_with=sorted(combined), changes=changes,
                        news=news, summary=c.summary, summary_is_machine=c.summary_is_machine, source_status=src_status,
                        disclaimer=DISCLAIMER)


def photo_spec(s: Session, f: ExtractedField) -> S.PhotoSpecOut:
    ev = s.scalar(select(FieldEvidence).where(FieldEvidence.extracted_field_id == f.id))
    v = f.value
    return S.PhotoSpecOut(id=f.id, item=v.get("item", "photo"), min_kb=v.get("min_kb"), max_kb=v.get("max_kb"), width=v.get("width"),
                          height=v.get("height"), formats=v.get("formats", []), evidence=evidence_out(s, ev.id) if ev else None)


def news_out(n: NewsItem) -> S.NewsOut:
    return S.NewsOut(id=n.id, title=n.title, url=n.url, publisher=n.publisher, published_at=n.published_at,
                     organisation_key=None, verified=False)


def search(s: Session, today: date, *, q: str | None, group: str | None, org: str | None, sector: str | None, status: str | None,
           date_from: date | None, date_to: date | None, ids: list[int] | None, page: int, page_size: int,
           sort: str = "deadline") -> S.Page[S.ExamSummary]:
    stmt = select(ExamCycle).join(Exam).join(Organisation).where(ExamCycle.retracted.is_(False))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(ExamCycle.title.ilike(like), Exam.name.ilike(like), ExamCycle.notification_number.ilike(like),
                              ExamCycle.id.in_(select(CategoryNumber.exam_cycle_id).where(CategoryNumber.number.ilike(like)))))
    if group:
        stmt = stmt.where(Organisation.group == group)
    if org:
        stmt = stmt.where(Organisation.key == org)
    if sector:
        stmt = stmt.where(Exam.sector == sector)
    if ids is not None:
        stmt = stmt.where(ExamCycle.id.in_(ids))
    if date_from or date_to:
        ev = select(Event.exam_cycle_id).where(Event.status == "active")
        if date_from:
            ev = ev.where(Event.date_start >= date_from)
        if date_to:
            ev = ev.where(Event.date_start <= date_to)
        stmt = stmt.where(ExamCycle.id.in_(ev))
    cycles = list(s.scalars(stmt))
    rows = [summary(s, c, today) for c in cycles]
    if status:
        wanted = set(status.split(","))
        rows = [r for r in rows if r.status in wanted]
    if sort == "recent":
        rows.sort(key=lambda r: r.updated_at, reverse=True)
    else:
        far = date(9999, 1, 1)
        rows.sort(key=lambda r: (r.status not in ("open", "upcoming", "exam_scheduled"),
                                 r.next_event.date_start if r.next_event and r.next_event.date_start else far, -r.id))
    total = len(rows)
    start = (page - 1) * page_size
    return S.Page[S.ExamSummary](items=rows[start:start + page_size], total=total, page=page, page_size=page_size)


def calendar(s: Session, start: date, end: date, ids: list[int] | None = None) -> list[S.CalendarEntry]:
    q = select(Event).join(ExamCycle).where(Event.status == "active", Event.date_start >= start, Event.date_start <= end,
                                             ExamCycle.retracted.is_(False))
    if ids is not None:
        q = q.where(Event.exam_cycle_id.in_(ids))
    out = []
    for e in s.scalars(q.order_by(Event.date_start)):
        c = s.get(ExamCycle, e.exam_cycle_id)
        out.append(S.CalendarEntry(date=e.date_start, date_end=e.date_end, exam_id=c.id, exam_title=c.title,
                                   organisation_key=c.exam.organisation.key, event_type=e.event_type, title=event_title(e),
                                   certainty=e.certainty, precision=e.precision, is_deadline=e.event_type in DEADLINE_EVENTS))
    return out


def rule_specs(s: Session, post: Post) -> list[RuleSpec]:
    out = []
    for r in s.scalars(select(EligibilityRule).where(EligibilityRule.post_id == post.id, EligibilityRule.status == "published")):
        ev = s.get(FieldEvidence, r.evidence_id) if r.evidence_id else None
        out.append(RuleSpec(r.rule_type, r.params, r.clause_text, ev.source_url if ev else None, ev.page if ev else None))
    return out


def eligibility(s: Session, c: ExamCycle, profile: Profile) -> S.ExamEligibility:
    posts = []
    cd: list[dict[str, Any]] = []
    for p in s.scalars(select(Post).where(Post.exam_cycle_id == c.id)):
        specs = rule_specs(s, p)
        ev = evaluate(specs, profile)
        posts.append(S.PostEligibility(post_id=p.id, post_name=p.name, status=ev.status,
                                       results=[S.RuleResultOut(**r.__dict__) for r in ev.results]))
        if not cd:
            cd = countdown(specs, profile, c.year)
    if not posts:
        overall = "needs_check"
    elif any(p.status == "eligible" for p in posts):
        overall = "eligible"
    elif all(p.status == "not_eligible" for p in posts):
        overall = "not_eligible"
    else:
        overall = "needs_check"
    return S.ExamEligibility(exam_id=c.id, exam_title=c.title, status=overall, posts=posts, countdown=cd)


def checklist(s: Session, c: ExamCycle, today: date, user_id: int | None) -> S.ChecklistOut:
    """Steps derived only from published official dates and published document specifications."""
    org = c.exam.organisation
    done = set()
    if user_id:
        done = set(s.scalars(select(UserChecklistItem.item_key).where(UserChecklistItem.user_id == user_id,
                                                                      UserChecklistItem.exam_cycle_id == c.id,
                                                                      UserChecklistItem.done.is_(True))))
    items: list[S.ChecklistItemOut] = []

    def add(key: str, text: str, ev: Event | None = None) -> None:
        src = evidence_out(s, ev.evidence_id).source_url if ev and ev.evidence_id and evidence_out(s, ev.evidence_id) else c.official_url
        items.append(S.ChecklistItemOut(key=key, text=text, due=ev.date_start if ev else None, certainty=ev.certainty if ev else None,
                                        source_url=src, done=key in done))

    add("read_notification", "Read the official notification fully, including eligibility and instructions.")
    if org.key == "kerala_psc":
        add("otr_profile", "Check your One Time Registration profile on Thulasi (name, date of birth, photo, signature).")
    if org.key == "kdrb":
        add("otr_profile", "Check your One Time Registration on the KDRB recruitment portal.")
    events = [e for e in _events(s, c.id) if e.status == "active"]
    by = {}
    for e in events:
        by.setdefault(e.event_type, []).append(e)
    if "application_end" in by:
        e = sorted(by["application_end"], key=lambda x: x.date_start)[-1]
        add("apply", f"Apply before the last date ({e.date_start:%d %b %Y}).", e)
    if "fee_deadline" in by:
        e = by["fee_deadline"][-1]
        add("fee", f"Pay the fee through the official portal by {e.date_start:%d %b %Y}.", e)
    if "confirmation_deadline" in by:
        e = sorted(by["confirmation_deadline"], key=lambda x: x.date_start)[-1]
        add("confirm", f"Submit confirmation on Thulasi by {e.date_start:%d %b %Y}. Without it you cannot write the exam.", e)
    if "admit_card" in by:
        e = by["admit_card"][0]
        add("admit_card", f"Download the admit card from {e.date_start:%d %b %Y}. Your centre and time are on it.", e)
    for e in sorted(by.get("exam", []), key=lambda x: x.date_start):
        add(f"exam_{e.id}", f"{event_title(e)}: {e.date_start:%d %b %Y}" + ("" if e.certainty == "official" else f" ({e.certainty})"), e)
    specs = [photo_spec(s, f) for f in s.scalars(select(ExtractedField).where(ExtractedField.exam_cycle_id == c.id,
                                                                            ExtractedField.status == "published",
                                                                            ExtractedField.field_name == "photo_spec"))]
    note = ("Steps come from the official dates we have verified. Check the notification for the full list of documents."
            if items else "No verified steps yet. Read the official notification.")
    return S.ChecklistOut(items=items, photo_specs=specs, certificate_rules=certificate_rules(s, c, by), note=note)


def certificate_rules(s: Session, c: ExamCycle, by: dict[str, list[Event]]) -> list[S.CertificateRuleOut]:
    """Certificate validity rules stated in the notice, with event-based limits resolved to dates."""
    out = []
    for f in s.scalars(select(ExtractedField).where(ExtractedField.exam_cycle_id == c.id, ExtractedField.status == "published",
                                                    ExtractedField.field_name == "certificate_rule")):
        v = f.value
        until = date.fromisoformat(v["issued_until"]) if v.get("issued_until") else None
        ev_name = v.get("until_event")
        if until is None and ev_name and by.get(ev_name):
            until = sorted(by[ev_name], key=lambda e: e.date_start)[-1].date_start
        frm = date.fromisoformat(v["issued_from"]) if v.get("issued_from") else None
        parts = [f"{v['certificate']} certificate"]
        if frm:
            parts.append(f"issued on or after {frm:%d %b %Y}")
        if until:
            parts.append(f"and not later than {until:%d %b %Y}" if frm else f"dated on or before {until:%d %b %Y}")
        elif ev_name == "interview":
            parts.append("and before your interview")
        if v.get("valid_year"):
            parts.append(f"valid for {v['valid_year']}")
        if v.get("financial_year"):
            parts.append(f"(income for financial year {v['financial_year']})")
        ev = s.scalar(select(FieldEvidence).where(FieldEvidence.extracted_field_id == f.id))
        out.append(S.CertificateRuleOut(certificate=v["certificate"], text=" ".join(parts) + ".", issued_from=frm, issued_until=until,
                                        financial_year=v.get("financial_year"), valid_year=v.get("valid_year"),
                                        evidence=evidence_out(s, ev.id) if ev else None))
    return out


def counts_by_org(s: Session) -> dict[str, int]:
    return dict(s.execute(select(Organisation.key, func.count(ExamCycle.id)).join(Exam, Exam.organisation_id == Organisation.id)
                          .join(ExamCycle, ExamCycle.exam_id == Exam.id).group_by(Organisation.key)).all())
