"""End-to-end flows required by the brief, run on saved official documents.

1. New notice -> publication -> matching -> notification
2. Revised date -> revision -> correct notification
"""

from datetime import date

from examradar_core.models import (
    CategoryNumber,
    Event,
    EventRevision,
    ExamCycle,
    FieldEvidence,
    Notification,
    NotificationPreference,
    ReviewTask,
    SavedExam,
    Source,
    SourceItem,
    User,
)
from examradar_worker import notify, ops
from examradar_worker.pipeline import Pipeline
from sqlalchemy import select

TODAY = date(2026, 11, 8)


def src(db, key):
    return db.scalar(select(Source).where(Source.key == key))


def make_user(db, interests=None):
    u = User(token_hash=f"h{db.scalar(select(User.id).order_by(User.id.desc())) or 0}x")
    db.add(u)
    db.flush()
    db.add(NotificationPreference(user_id=u.id, enabled_types=list(notify.DEFAULT_TYPES), interests=interests or {},
                                  quiet_start="23:00", quiet_end="05:00"))
    db.flush()
    return u


def test_kerala_psc_notice_to_published_dates_with_evidence(db, client):
    p = Pipeline(db, client=client, today=TODAY)
    run = p.run_source(src(db, "kerala_psc:https://keralapsc.gov.in/notifications"))
    assert run.status == "ok" and run.items_found >= 15
    p.process_documents(10)
    db.commit()
    cn = db.scalar(select(CategoryNumber).where(CategoryNumber.number == "162/2026"))
    cycle = db.get(ExamCycle, cn.exam_cycle_id)
    assert "Laboratory Assistant" in cycle.title
    ev = db.scalar(select(Event).where(Event.exam_cycle_id == cycle.id, Event.event_type == "application_end"))
    assert ev.date_start == date(2026, 12, 2) and ev.certainty == "official"
    evidence = db.get(FieldEvidence, ev.evidence_id)
    assert evidence.source_url.startswith("https://keralapsc.gov.in/") and evidence.document_hash and evidence.quote
    # Age rule extracted from the real notification, with the supporting clause.
    from examradar_core.models import EligibilityRule, Post

    post = db.scalar(select(Post).where(Post.exam_cycle_id == cycle.id))
    rule = db.scalar(select(EligibilityRule).where(EligibilityRule.post_id == post.id, EligibilityRule.rule_type == "age",
                                                   EligibilityRule.status == "published"))
    assert rule.params["from"] == "1982-01-02" and rule.params["to"] == "2008-01-01"
    assert post.vacancies == 1


def test_programme_creates_confirmation_and_exam_events(db, client):
    p = Pipeline(db, client=client, today=TODAY)
    p.run_source(src(db, "kerala_psc:https://keralapsc.gov.in/examinations"))
    p.process_documents(5)
    db.commit()
    exams = db.scalars(select(Event).where(Event.event_type == "exam")).all()
    confs = db.scalars(select(Event).where(Event.event_type == "confirmation_deadline")).all()
    assert len(exams) >= 15
    assert confs and all(e.date_start == date(2026, 11, 14) for e in confs)
    cn = db.scalar(select(CategoryNumber).where(CategoryNumber.number == "698/2025"))
    e = db.scalar(select(Event).where(Event.exam_cycle_id == cn.exam_cycle_id, Event.event_type == "exam"))
    assert e.date_start == date(2027, 1, 12)


def test_new_notice_alert_then_matching_notification(db, client, transport):
    """Second crawl finds a new gazette row: fast alert to interested users, no dates in it."""
    s = src(db, "kerala_psc:https://keralapsc.gov.in/latest")
    p = Pipeline(db, client=client, today=TODAY)
    p.run_source(s)  # baseline: nothing is announced
    user = make_user(db, {"organisations": ["kerala_psc"]})
    db.commit()
    assert not db.scalars(select(Notification)).all()
    html = (transport.overrides.get(s.url) or open("data/fixtures/kerala_psc/latest.html", "rb").read())
    new_row = (b'<tr><td>0</td><td>Short List</td><td>Village Field Assistant (Cat.No. 001/2026) in Revenue Department.</td>'
               b'<td><p>Short List No. : 999/2026/DOD wef 08.11.2026.</p></td>'
               b'<td><a class="down-link" href="/sites/default/files/2026-11/fixture-shortlist.pdf">Download</a></td></tr>')
    transport.overrides[s.url] = html.replace(b"<tbody>", b"<tbody>" + new_row, 1)
    p2 = Pipeline(db, client=client, today=TODAY)
    run = p2.run_source(s)
    db.commit()
    assert run.new_items == 1
    n = db.scalar(select(Notification).where(Notification.user_id == user.id))
    assert n.type == "new_notice" and "001/2026" in n.body
    assert not any(ch.isdigit() and "2026" in n.title for ch in n.title)  # fast alert title carries no dates
    # Delivered to the inbox (no push configured in tests), exactly once.
    assert notify.dispatch(db) >= 1
    assert notify.dispatch(db) == 0


def test_revised_date_goes_to_review_then_revision_and_notification(db, client, transport):
    s = src(db, "kerala_psc:https://keralapsc.gov.in/notifications")
    p = Pipeline(db, client=client, today=TODAY)
    p.run_source(s)
    db.commit()
    cn = db.scalar(select(CategoryNumber).where(CategoryNumber.number == "162/2026"))
    user = make_user(db)
    db.add(SavedExam(user_id=user.id, exam_cycle_id=cn.exam_cycle_id))
    db.commit()
    html = open("data/fixtures/kerala_psc/notifications.html", "rb").read()
    transport.overrides[s.url] = html.replace(b'<time datetime="2026-12-02T12:00:00Z">02-12-2026</time>',
                                              b'<time datetime="2026-12-09T12:00:00Z">09-12-2026</time>', 1)
    Pipeline(db, client=client, today=TODAY).run_source(s)
    db.commit()
    ev = db.scalar(select(Event).where(Event.exam_cycle_id == cn.exam_cycle_id, Event.event_type == "application_end"))
    assert ev.date_start == date(2026, 12, 2), "a changed published date must not change before review"
    task = db.scalar(select(ReviewTask).where(ReviewTask.kind == "revision", ReviewTask.status == "open"))
    assert task and "2026-12-09" in task.reason
    ops.approve_task(db, task.id, "admin@test")
    db.commit()
    db.refresh(ev)
    assert ev.date_start == date(2026, 12, 9) and ev.revision_count == 2
    revs = db.scalars(select(EventRevision).where(EventRevision.event_id == ev.id).order_by(EventRevision.revision_no)).all()
    assert revs[0].new_value["date_start"] == "2026-12-02" and revs[1].old_value["date_start"] == "2026-12-02"
    n = db.scalar(select(Notification).where(Notification.user_id == user.id, Notification.type == "date_change"))
    assert n and "09 Dec 2026" in n.body and "was 2026-12-02" in n.body
    # Retraction sends a correction to the same users.
    ops.retract_event(db, ev.id, "admin@test", "Published in error")
    db.commit()
    assert db.scalar(select(Notification).where(Notification.user_id == user.id, Notification.type == "correction"))


def test_deadline_reminders_are_idempotent_and_skip_expected(db, client):
    p = Pipeline(db, client=client, today=TODAY)
    p.run_source(src(db, "kerala_psc:https://keralapsc.gov.in/notifications"))
    cn = db.scalar(select(CategoryNumber).where(CategoryNumber.number == "162/2026"))
    user = make_user(db)
    db.add(SavedExam(user_id=user.id, exam_cycle_id=cn.exam_cycle_id))
    db.commit()
    assert notify.deadline_reminders(db, date(2026, 11, 25)) == 1  # 7 days before 2 Dec
    assert notify.deadline_reminders(db, date(2026, 11, 25)) == 0  # idempotent
    ev = db.scalar(select(Event).where(Event.exam_cycle_id == cn.exam_cycle_id, Event.event_type == "application_end"))
    ev.certainty = "expected"
    db.commit()
    assert notify.deadline_reminders(db, date(2026, 11, 29)) == 0  # expected dates never drive deadline reminders


def test_upsc_exam_page_notice_extracts_key_dates(db, client):
    p = Pipeline(db, client=client, today=TODAY)
    p.run_source(src(db, "upsc:https://www.upsc.gov.in/examinations/active-exams"))
    p.process_documents(5)
    db.commit()
    cycle = db.scalar(select(ExamCycle).where(ExamCycle.title == "Engineering Services Examination, 2027"))
    evs = {(e.event_type, e.label): e.date_start for e in db.scalars(select(Event).where(Event.exam_cycle_id == cycle.id))}
    assert evs[("application_end", None)] == date(2026, 10, 6)
    assert evs[("exam", "Exam date (Preliminary)")] == date(2027, 1, 31)
    assert cycle.notification_number == "02/2027-ENGG"


def test_blocked_source_is_marked_and_not_retried(db, client, transport):
    s = src(db, "rrb:https://rrb.indianrailways.gov.in/thiruvananthapuram")
    transport.overrides[s.url] = (200, open("data/fixtures/rrb/blocked_getdata.html", "rb").read())
    run = Pipeline(db, client=client, today=TODAY).run_source(s)
    db.commit()
    assert run.status == "blocked" and s.status == "blocked"
    assert db.scalar(select(ReviewTask).where(ReviewTask.kind == "source_health", ReviewTask.source_id == s.id))
    assert s not in Pipeline(db, client=client, today=TODAY).due_sources()


def test_news_signal_creates_candidate_and_triggers_recheck(db, client):
    news = src(db, "news_indianexpress_jobs")
    p = Pipeline(db, client=client, today=TODAY)
    run = p.run_news(news)
    db.commit()
    from examradar_core.models import MissedNoticeCandidate, NewsItem

    assert run.new_items > 10
    assert db.scalars(select(NewsItem)).first().public is True
    assert db.scalars(select(MissedNoticeCandidate)).first() is not None
    assert not db.scalars(select(SourceItem)).all(), "news never becomes official items"


def test_new_matching_exam_for_users_with_stored_profile(db, client):
    from examradar_core.models import UserProfile

    eligible = make_user(db, {"organisations": ["kerala_psc"]})
    db.add(UserProfile(user_id=eligible.id, data={"date_of_birth": "1995-05-05", "category": "GEN"}))
    too_old = make_user(db, {"organisations": ["kerala_psc"]})
    db.add(UserProfile(user_id=too_old.id, data={"date_of_birth": "1960-05-05", "category": "GEN", "pwd": False, "ex_serviceman": False}))
    no_profile = make_user(db, {"organisations": ["kerala_psc"]})
    db.commit()
    p = Pipeline(db, client=client, today=TODAY)
    p.run_source(src(db, "kerala_psc:https://keralapsc.gov.in/notifications"))
    p.process_documents(40)
    db.commit()
    got = {n.user_id for n in db.scalars(select(Notification).where(Notification.type == "new_matching_exam"))}
    assert eligible.id in got and too_old.id not in got and no_profile.id not in got
