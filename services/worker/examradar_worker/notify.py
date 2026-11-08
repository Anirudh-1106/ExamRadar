"""Notifications: who to tell, deduplication, quiet hours, daily caps, bundling, and delivery."""

import hashlib
import json
import logging
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol

from examradar_core.enums import EVENT_TYPES, NOTIFICATION_TYPES, REMINDER_CERTAINTY, URGENT_TYPES
from examradar_core.models import (
    Device,
    Event,
    EventRevision,
    ExamCycle,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    SavedExam,
    UserExamStatus,
)
from examradar_core.settings import get_settings
from examradar_core.timeutil import IST, to_ist, utcnow
from sqlalchemy import func, select
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

DEFAULT_TYPES = list(NOTIFICATION_TYPES)


def idem_key(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


def fmt_date(ev: Event) -> str:
    if not ev.date_start:
        return "date to be announced"
    d = ev.date_start.strftime("%B %Y") if ev.precision == "month" else ev.date_start.strftime("%d %b %Y")
    if ev.date_end and ev.date_end != ev.date_start:
        d += " to " + ev.date_end.strftime("%d %b %Y")
    if ev.certainty != "official":
        d += f" ({ev.certainty})"
    return d


def prefs_for(s: Session, user_id: int) -> NotificationPreference:
    p = s.get(NotificationPreference, user_id)
    if p is None:
        p = NotificationPreference(user_id=user_id, enabled_types=DEFAULT_TYPES, interests={})
        s.add(p)
        s.flush()
    return p


def create(s: Session, user_id: int, ntype: str, title: str, body: str, deep_link: str, *, cycle_id: int | None = None,
           event_id: int | None = None, revision_id: int | None = None, extra: str = "") -> Notification | None:
    p = prefs_for(s, user_id)
    if ntype not in (p.enabled_types or DEFAULT_TYPES) and ntype not in ("correction",):
        return None
    key = idem_key(user_id, ntype, cycle_id, event_id, revision_id, extra)
    if s.scalar(select(Notification.id).where(Notification.idempotency_key == key)):
        return None
    n = Notification(user_id=user_id, type=ntype, title=title[:300], body=body, deep_link=deep_link, exam_cycle_id=cycle_id,
                     event_id=event_id, revision_id=revision_id, idempotency_key=key, urgent=ntype in URGENT_TYPES)
    s.add(n)
    s.flush()
    return n


def users_for_cycle(s: Session, cycle_id: int) -> set[int]:
    saved = set(s.scalars(select(SavedExam.user_id).where(SavedExam.exam_cycle_id == cycle_id)))
    tracked = set(s.scalars(select(UserExamStatus.user_id).where(UserExamStatus.exam_cycle_id == cycle_id)))
    return saved | tracked


def users_interested(s: Session, org_key: str, group: str | None, sector: str | None) -> set[int]:
    out = set()
    for p in s.scalars(select(NotificationPreference)):
        i = p.interests or {}
        if org_key in i.get("organisations", []) or (group and group in i.get("groups", [])) or (sector and sector in i.get("sectors", [])):
            out.add(p.user_id)
    return out


def on_new_notice(s: Session, cycle: ExamCycle | None, org_key: str, group: str, title: str, item_id: int) -> int:
    sector = cycle.exam.sector if cycle else None
    users = users_interested(s, org_key, group, sector)
    if cycle:
        users |= users_for_cycle(s, cycle.id)
    link = f"examradar://exam/{cycle.id}" if cycle else f"examradar://notice/{item_id}"
    count = 0
    for u in users:
        if create(s, u, "new_notice", "New official notice detected", title, link, cycle_id=cycle.id if cycle else None,
                  extra=f"item:{item_id}"):
            count += 1
    return count


TYPE_FOR_EVENT = {"admit_card": "admit_card", "answer_key": "answer_key", "objection_deadline": "objection_deadline",
                  "result": "result", "ranked_list": "result", "short_list": "result", "correction_window": "correction_window",
                  "confirmation_deadline": "confirmation_deadline", "application_start": "application_opening"}


def on_event_published(s: Session, ev: Event, rev: EventRevision) -> int:
    cycle = s.get(ExamCycle, ev.exam_cycle_id)
    label = ev.label or EVENT_TYPES.get(ev.event_type, ev.event_type)
    if rev.kind == "create":
        ntype = TYPE_FOR_EVENT.get(ev.event_type)
        if not ntype:
            return 0
        title, body = f"{label}: {cycle.title}"[:300], f"{label} {fmt_date(ev)}. Confirm on the official website."
    elif rev.kind in ("retract", "correction"):
        ntype, title = "correction", f"Correction: {cycle.title}"[:300]
        body = f"An earlier update about {label.lower()} was withdrawn. {rev.reason or ''}".strip()
    else:
        ntype, title = "date_change", f"Date changed: {cycle.title}"[:300]
        old = (rev.old_value or {}).get("date_start")
        body = f"{label} is now {fmt_date(ev)}" + (f" (was {old})" if old else "") + ". Source: official notice."
    n = 0
    for u in users_for_cycle(s, cycle.id):
        if create(s, u, ntype, title, body, f"examradar://exam/{cycle.id}?tab=changes" if rev.kind != "create" else f"examradar://exam/{cycle.id}",
                  cycle_id=cycle.id, event_id=ev.id, revision_id=rev.id):
            n += 1
    return n


def on_link_changed(s: Session, cycle: ExamCycle, link) -> int:
    n = 0
    for u in users_for_cycle(s, cycle.id):
        if create(s, u, "link_change", f"Application link changed: {cycle.title}"[:300],
                  f"The official application link is now on {link.host}. Use only this link.", f"examradar://exam/{cycle.id}",
                  cycle_id=cycle.id, extra=f"link:{link.id}"):
            n += 1
    return n


def on_new_matching_exam(s: Session, cycle: ExamCycle, today: date | None = None) -> int:
    """Users who stored a profile (with consent) and follow this organisation, group, or sector, and who may apply."""
    from examradar_core.models import EligibilityRule, Post, UserProfile
    from examradar_core.timeutil import ist_today
    from examradar_eligibility import Profile, RuleSpec, evaluate

    still_open = s.scalar(select(Event.id).where(Event.exam_cycle_id == cycle.id, Event.event_type == "application_end",
                                                 Event.status == "active", Event.date_start >= (today or ist_today())))
    if not still_open:
        return 0
    exam = cycle.exam
    users = users_interested(s, exam.organisation.key, exam.organisation.group, exam.sector) - users_for_cycle(s, cycle.id)
    posts = s.scalars(select(Post).where(Post.exam_cycle_id == cycle.id)).all()
    n = 0
    for uid in users:
        prof = s.get(UserProfile, uid)
        if prof is None or not posts:
            continue
        p = Profile.from_dict(prof.data)
        ok = False
        for post in posts:
            rules = [RuleSpec(r.rule_type, r.params) for r in s.scalars(select(EligibilityRule).where(
                EligibilityRule.post_id == post.id, EligibilityRule.status == "published"))]
            if rules and evaluate(rules, p).status != "not_eligible":
                ok = True
                break
        if ok and create(s, uid, "new_matching_exam", f"New exam you may be able to apply for: {cycle.title}"[:300],
                         "Based on your saved details and the official notification. Check the notice before applying.",
                         f"examradar://exam/{cycle.id}", cycle_id=cycle.id):
            n += 1
    return n


def deadline_reminders(s: Session, today: date) -> int:
    """7, 3, and 1 days before deadlines from official or tentative dates. Expected dates never trigger these."""
    created = 0
    offsets = {7: "deadline_7", 3: "deadline_3", 1: "deadline_1"}
    targets = [today + timedelta(days=d) for d in offsets]
    q = select(Event).where(Event.status == "active", Event.precision == "day", Event.date_start.in_(targets),
                            Event.certainty.in_(REMINDER_CERTAINTY),
                            Event.event_type.in_(["application_end", "fee_deadline", "confirmation_deadline", "objection_deadline"]))
    for ev in s.scalars(q):
        days = (ev.date_start - today).days
        ntype = "confirmation_deadline" if ev.event_type == "confirmation_deadline" and days == 1 else offsets[days]
        cycle = s.get(ExamCycle, ev.exam_cycle_id)
        label = EVENT_TYPES.get(ev.event_type, ev.event_type)
        when = "tomorrow" if days == 1 else f"in {days} days"
        for u in users_for_cycle(s, cycle.id):
            st = s.scalar(select(UserExamStatus.status).where(UserExamStatus.user_id == u, UserExamStatus.exam_cycle_id == cycle.id))
            if ev.event_type == "application_end" and st in ("applied", "confirmed", "admit_card", "exam_taken", "result_checked"):
                continue
            if create(s, u, ntype, f"{label} {when}: {cycle.title}"[:300], f"{label}: {fmt_date(ev)}.",
                      f"examradar://exam/{cycle.id}", cycle_id=cycle.id, event_id=ev.id, extra=f"offset:{days}:{ev.date_start}"):
                created += 1
    return created


def in_quiet_hours(p: NotificationPreference, now_utc: datetime) -> bool:
    local = to_ist(now_utc).time()
    start, end = time.fromisoformat(p.quiet_start), time.fromisoformat(p.quiet_end)
    return (start <= local or local < end) if start > end else (start <= local < end)


class PushSender(Protocol):
    def send(self, token: str, title: str, body: str, data: dict) -> tuple[bool, str | None]: ...


class NoPushSender:
    def send(self, token: str, title: str, body: str, data: dict) -> tuple[bool, str | None]:
        return False, "push not configured"


class FcmSender:  # pragma: no cover - needs Firebase credentials
    def __init__(self, project_id: str, credentials_file: str):
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        self.project_id = project_id
        self.creds = service_account.Credentials.from_service_account_file(
            credentials_file, scopes=["https://www.googleapis.com/auth/firebase.messaging"])
        self._req = Request

    def send(self, token: str, title: str, body: str, data: dict) -> tuple[bool, str | None]:
        import httpx

        if not self.creds.valid:
            self.creds.refresh(self._req())
        r = httpx.post(f"https://fcm.googleapis.com/v1/projects/{self.project_id}/messages:send",
                       headers={"Authorization": f"Bearer {self.creds.token}"},
                       json={"message": {"token": token, "notification": {"title": title, "body": body},
                                         "data": {k: str(v) for k, v in data.items()},
                                         "android": {"priority": "high"}}}, timeout=20)
        return (r.status_code == 200, None if r.status_code == 200 else r.text[:300])


def get_sender() -> PushSender:
    s = get_settings()
    if s.firebase_project_id and s.firebase_credentials_file:
        try:
            return FcmSender(s.firebase_project_id, s.firebase_credentials_file)
        except Exception as e:  # pragma: no cover
            log.warning("fcm unavailable", extra={"data": {"error": str(e)[:200]}})
    return NoPushSender()


def dispatch(s: Session, sender: PushSender | None = None, now: datetime | None = None, bundle_over: int = 3) -> int:
    """Deliver pending notifications. Urgent ones ignore quiet hours and daily caps."""
    sender = sender or get_sender()
    now = now or utcnow()
    day_start = datetime.combine(to_ist(now).date(), time(0), tzinfo=IST).astimezone(UTC).replace(tzinfo=None)
    sent = 0
    pending = s.scalars(select(Notification).where(Notification.status.in_(["pending", "held"])).order_by(Notification.id)).all()
    by_user: dict[int, list[Notification]] = {}
    for n in pending:
        by_user.setdefault(n.user_id, []).append(n)
    for uid, items in by_user.items():
        p = prefs_for(s, uid)
        quiet = in_quiet_hours(p, now)
        sent_today = s.scalar(select(func.count(Notification.id)).where(
            Notification.user_id == uid, Notification.status.in_(["sent", "bundled"]), Notification.created_at >= day_start)) or 0
        urgent = [n for n in items if n.urgent]
        normal = [n for n in items if not n.urgent]
        to_send: list[tuple[str, str, str, list[Notification]]] = [(n.title, n.body, n.deep_link, [n]) for n in urgent]
        if normal and not quiet:
            room = max(0, p.max_per_day - sent_today)
            if room == 0:
                for n in normal:
                    n.status = "held"
            elif p.digest and len(normal) > bundle_over:
                to_send.append((f"{len(normal)} updates for your exams", "; ".join(n.title for n in normal[:4])[:500],
                                "examradar://alerts", normal))
            else:
                for n in normal[:room]:
                    to_send.append((n.title, n.body, n.deep_link, [n]))
                for n in normal[room:]:
                    n.status = "held"
        devices = s.scalars(select(Device).where(Device.user_id == uid, Device.fcm_token.is_not(None))).all()
        for title, body, link, group in to_send:
            ok_any = False
            for d in devices:
                ok, err = sender.send(d.fcm_token, title, body, {"deep_link": link, "ids": json.dumps([g.id for g in group])})
                s.add(NotificationDelivery(notification_id=group[0].id, device_id=d.id, channel="fcm",
                                           status="sent" if ok else "failed", error=err))
                ok_any = ok_any or ok
            if not devices:
                s.add(NotificationDelivery(notification_id=group[0].id, channel="inbox", status="inbox_only"))
            for g in group:
                g.status = "bundled" if len(group) > 1 else "sent"
                g.bundle_key = idem_key(*(x.id for x in group)) if len(group) > 1 else None
            sent += 1
    s.flush()
    return sent
