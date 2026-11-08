"""Database schema. Revisions are append-only; nothing that users have seen is overwritten in place."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .timeutil import utcnow


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


def _pk() -> Mapped[int]:
    return mapped_column(Integer, primary_key=True)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime, default=utcnow, nullable=False)


# ---------------------------------------------------------------- organisations and sources


class Organisation(Base):
    __tablename__ = "organisations"
    id: Mapped[int] = _pk()
    key: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    group: Mapped[str] = mapped_column(String(20))  # central | kerala
    collection: Mapped[str] = mapped_column(String(30), default="auto")  # auto | manual | pending_decision
    created_at: Mapped[datetime] = _created()
    sources: Mapped[list["Source"]] = relationship(back_populates="organisation")
    domains: Mapped[list["OfficialDomain"]] = relationship(back_populates="organisation")


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = _pk()
    organisation_id: Mapped[int | None] = mapped_column(ForeignKey("organisations.id"))
    key: Mapped[str] = mapped_column(String(120), unique=True)
    adapter: Mapped[str] = mapped_column(String(50))
    url: Mapped[str] = mapped_column(String(1000))
    kind: Mapped[str] = mapped_column(String(20), default="listing")  # listing|sitemap|rss|news|manual
    is_official: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    every_minutes: Mapped[int] = mapped_column(Integer, default=120)
    active_deadline_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="new")  # ok|stale|failing|blocked|manual|disabled|new
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_new_item_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    runs_total: Mapped[int] = mapped_column(Integer, default=0)
    runs_failed: Mapped[int] = mapped_column(Integer, default=0)
    last_parser_yield: Mapped[int | None] = mapped_column(Integer)
    expected_silence_hours: Mapped[int] = mapped_column(Integer, default=24 * 14)
    etag: Mapped[str | None] = mapped_column(String(300))
    last_modified: Mapped[str | None] = mapped_column(String(100))
    last_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = _created()
    organisation: Mapped[Organisation | None] = relationship(back_populates="sources")


class OfficialDomain(Base):
    __tablename__ = "official_domains"
    __table_args__ = (UniqueConstraint("organisation_id", "host", "path_prefix", "purpose"),)
    id: Mapped[int] = _pk()
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id"))
    host: Mapped[str] = mapped_column(String(255), index=True)
    path_prefix: Mapped[str] = mapped_column(String(300), default="/")
    purpose: Mapped[str] = mapped_column(String(20))  # content | apply | portal
    verified_at: Mapped[date | None] = mapped_column(Date)
    verified_by: Mapped[str | None] = mapped_column(String(100))
    note: Mapped[str | None] = mapped_column(String(300))
    organisation: Mapped[Organisation] = relationship(back_populates="domains")


class CrawlRun(Base):
    __tablename__ = "crawl_runs"
    id: Mapped[int] = _pk()
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    started_at: Mapped[datetime] = _created()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|ok|unchanged|failed|blocked|robots
    http_status: Mapped[int | None] = mapped_column(Integer)
    items_found: Mapped[int] = mapped_column(Integer, default=0)
    new_items: Mapped[int] = mapped_column(Integer, default=0)
    bytes: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class SourceSnapshot(Base):
    __tablename__ = "source_snapshots"
    id: Mapped[int] = _pk()
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    crawl_run_id: Mapped[int | None] = mapped_column(ForeignKey("crawl_runs.id"))
    url: Mapped[str] = mapped_column(String(1000))
    fetched_at: Mapped[datetime] = _created()
    http_status: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(120))
    raw_hash: Mapped[str] = mapped_column(String(64))
    normalized_hash: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(300))
    normalized_text: Mapped[str | None] = mapped_column(Text)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = _pk()
    organisation_id: Mapped[int | None] = mapped_column(ForeignKey("organisations.id"))
    url: Mapped[str] = mapped_column(String(1000), index=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(300))
    content_type: Mapped[str] = mapped_column(String(120))
    size: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(500))
    kind: Mapped[str | None] = mapped_column(String(40))
    published_on: Mapped[date | None] = mapped_column(Date)
    first_seen_at: Mapped[datetime] = _created()
    retrieved_at: Mapped[datetime] = _created()
    last_checked_at: Mapped[datetime] = _created()
    page_count: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(Text)
    pages_text: Mapped[list[Any] | None] = mapped_column(JSON)
    text_quality: Mapped[float | None] = mapped_column(Float)
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str | None] = mapped_column(String(20))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)


class SourceItem(Base):
    """One entry discovered on a listing page, keyed by a stable identity."""

    __tablename__ = "source_items"
    __table_args__ = (UniqueConstraint("source_id", "item_key"),)
    id: Mapped[int] = _pk()
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    item_key: Mapped[str] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(1000))
    kind: Mapped[str] = mapped_column(String(40), default="notice")
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    first_seen_at: Mapped[datetime] = _created()
    last_seen_at: Mapped[datetime] = _created()
    published_hint: Mapped[datetime | None] = mapped_column(DateTime)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    exam_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("exam_cycles.id"))
    fast_alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------- exams


class Exam(Base):
    """A recurring exam family, for example 'Kerala PSC Laboratory Assistant' or 'UPSC ESE'."""

    __tablename__ = "exams"
    id: Mapped[int] = _pk()
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id"), index=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(400))
    sector: Mapped[str | None] = mapped_column(String(40))  # psc|banking|railway|teaching|defence|devaswom|other
    created_at: Mapped[datetime] = _created()
    organisation: Mapped[Organisation] = relationship()
    cycles: Mapped[list["ExamCycle"]] = relationship(back_populates="exam")


class ExamCycle(Base):
    """A specific notification or year of an exam."""

    __tablename__ = "exam_cycles"
    id: Mapped[int] = _pk()
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), index=True)
    title: Mapped[str] = mapped_column(String(600))
    year: Mapped[int | None] = mapped_column(Integer)
    notification_number: Mapped[str | None] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(30), default="notice")  # notice|upcoming|open|closed|exam|result|cancelled
    official_url: Mapped[str] = mapped_column(String(1000))
    notification_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    is_fast_alert: Mapped[bool] = mapped_column(Boolean, default=False)
    vacancies_total: Mapped[int | None] = mapped_column(Integer)
    fee_summary: Mapped[list[Any] | None] = mapped_column(JSON)
    qualification_text: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    summary_is_machine: Mapped[bool] = mapped_column(Boolean, default=True)
    published_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _created()
    last_checked_at: Mapped[datetime] = _created()
    retracted: Mapped[bool] = mapped_column(Boolean, default=False)
    exam: Mapped[Exam] = relationship(back_populates="cycles")
    posts: Mapped[list["Post"]] = relationship(back_populates="cycle")
    events: Mapped[list["Event"]] = relationship(back_populates="cycle")
    links: Mapped[list["Link"]] = relationship(back_populates="cycle")


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = _pk()
    exam_cycle_id: Mapped[int] = mapped_column(ForeignKey("exam_cycles.id"), index=True)
    name: Mapped[str] = mapped_column(String(500))
    department: Mapped[str | None] = mapped_column(String(500))
    vacancies: Mapped[int | None] = mapped_column(Integer)
    vacancies_text: Mapped[str | None] = mapped_column(String(300))
    pay_scale: Mapped[str | None] = mapped_column(String(200))
    category_number_id: Mapped[int | None] = mapped_column(ForeignKey("category_numbers.id"))
    cycle: Mapped[ExamCycle] = relationship(back_populates="posts")
    rules: Mapped[list["EligibilityRule"]] = relationship(back_populates="post")


class CategoryNumber(Base):
    """Kerala PSC and KDRB category numbers such as 162/2026."""

    __tablename__ = "category_numbers"
    __table_args__ = (UniqueConstraint("organisation_id", "number"),)
    id: Mapped[int] = _pk()
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id"))
    number: Mapped[str] = mapped_column(String(30), index=True)
    year: Mapped[int | None] = mapped_column(Integer)
    post_title: Mapped[str | None] = mapped_column(String(600))
    exam_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("exam_cycles.id"))


class ExamCategoryLink(Base):
    """Links a common preliminary exam (or any combined exam) to many category numbers."""

    __tablename__ = "exam_category_links"
    __table_args__ = (UniqueConstraint("exam_cycle_id", "category_number_id"),)
    id: Mapped[int] = _pk()
    exam_cycle_id: Mapped[int] = mapped_column(ForeignKey("exam_cycles.id"))
    category_number_id: Mapped[int] = mapped_column(ForeignKey("category_numbers.id"))
    role: Mapped[str] = mapped_column(String(30), default="combined_prelims")


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = _pk()
    exam_cycle_id: Mapped[int] = mapped_column(ForeignKey("exam_cycles.id"), index=True)
    post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id"))
    category_number: Mapped[str | None] = mapped_column(String(30))
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    label: Mapped[str | None] = mapped_column(String(300))
    date_start: Mapped[date | None] = mapped_column(Date, index=True)
    date_end: Mapped[date | None] = mapped_column(Date)
    precision: Mapped[str] = mapped_column(String(10), default="day")  # day | month
    time_text: Mapped[str | None] = mapped_column(String(100))
    certainty: Mapped[str] = mapped_column(String(12))  # official | tentative | expected
    status: Mapped[str] = mapped_column(String(15), default="active")  # active | retracted | cancelled
    revision_count: Mapped[int] = mapped_column(Integer, default=1)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("field_evidence.id"))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _created()
    cycle: Mapped[ExamCycle] = relationship(back_populates="events")
    revisions: Mapped[list["EventRevision"]] = relationship(back_populates="event", order_by="EventRevision.id")


class EventRevision(Base):
    __tablename__ = "event_revisions"
    id: Mapped[int] = _pk()
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    revision_no: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(15))  # create | update | retract | correction | cancel
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("field_evidence.id"))
    created_by: Mapped[str] = mapped_column(String(100), default="pipeline")
    created_at: Mapped[datetime] = _created()
    event: Mapped[Event] = relationship(back_populates="revisions")


class Link(Base):
    __tablename__ = "links"
    id: Mapped[int] = _pk()
    exam_cycle_id: Mapped[int] = mapped_column(ForeignKey("exam_cycles.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # apply|notification|official_page|syllabus|admit_card|result|answer_key|other
    url: Mapped[str] = mapped_column(String(1500))
    label: Mapped[str | None] = mapped_column(String(300))
    host: Mapped[str] = mapped_column(String(255))
    allowlisted: Mapped[bool] = mapped_column(Boolean, default=False)
    copy_hint: Mapped[str | None] = mapped_column(String(100))  # e.g. Kerala PSC category number to copy
    created_at: Mapped[datetime] = _created()
    cycle: Mapped[ExamCycle] = relationship(back_populates="links")


# ---------------------------------------------------------------- extraction and review


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"
    id: Mapped[int] = _pk()
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    extractor: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(20))
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="ok")
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = _created()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class ExtractedField(Base):
    __tablename__ = "extracted_fields"
    id: Mapped[int] = _pk()
    extraction_run_id: Mapped[int] = mapped_column(ForeignKey("extraction_runs.id"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    exam_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("exam_cycles.id"))
    field_name: Mapped[str] = mapped_column(String(80))
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(20))  # rule | table | llm | manual
    status: Mapped[str] = mapped_column(String(20), default="candidate")  # candidate|published|needs_review|rejected
    validation_errors: Mapped[list[Any] | None] = mapped_column(JSON)
    impact: Mapped[str] = mapped_column(String(10), default="low")
    created_at: Mapped[datetime] = _created()
    evidence: Mapped[list["FieldEvidence"]] = relationship(back_populates="field")


class FieldEvidence(Base):
    __tablename__ = "field_evidence"
    id: Mapped[int] = _pk()
    extracted_field_id: Mapped[int | None] = mapped_column(ForeignKey("extracted_fields.id"), index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    document_hash: Mapped[str | None] = mapped_column(String(64))
    source_url: Mapped[str] = mapped_column(String(1000))
    page: Mapped[int | None] = mapped_column(Integer)
    quote: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
    published_on: Mapped[date | None] = mapped_column(Date)
    retrieved_at: Mapped[datetime] = _created()
    last_checked_at: Mapped[datetime] = _created()
    field: Mapped[ExtractedField | None] = relationship(back_populates="evidence")


class ReviewTask(Base):
    __tablename__ = "review_tasks"
    id: Mapped[int] = _pk()
    kind: Mapped[str] = mapped_column(String(30))  # field|conflict|revision|missed_notice|manual_check|source_health
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|approved|rejected|edited|dismissed
    priority: Mapped[int] = mapped_column(Integer, default=2)  # 1 urgent .. 3 low
    reason: Mapped[str] = mapped_column(Text)
    extracted_field_id: Mapped[int | None] = mapped_column(ForeignKey("extracted_fields.id"))
    exam_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("exam_cycles.id"))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = _created()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved_by: Mapped[str | None] = mapped_column(String(100))
    resolution: Mapped[dict[str, Any] | None] = mapped_column(JSON)


# ---------------------------------------------------------------- eligibility


class QualificationTaxonomy(Base):
    __tablename__ = "qualification_taxonomy"
    id: Mapped[int] = _pk()
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    level: Mapped[int] = mapped_column(Integer)
    parent_code: Mapped[str | None] = mapped_column(String(60))
    aliases: Mapped[list[Any] | None] = mapped_column(JSON)


class EligibilityRule(Base):
    __tablename__ = "eligibility_rules"
    id: Mapped[int] = _pk()
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    rule_type: Mapped[str] = mapped_column(String(40))
    params: Mapped[dict[str, Any]] = mapped_column(JSON)
    clause_text: Mapped[str | None] = mapped_column(Text)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("field_evidence.id"))
    status: Mapped[str] = mapped_column(String(20), default="published")
    post: Mapped[Post] = relationship(back_populates="rules")


class RelaxationRule(Base):
    __tablename__ = "relaxation_rules"
    id: Mapped[int] = _pk()
    exam_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("exam_cycles.id"))
    post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id"))
    applies_to: Mapped[str] = mapped_column(String(40))  # OBC|SC|ST|PWBD|EXSM|WIDOW|GOVT_SERVANT ...
    years: Mapped[int] = mapped_column(Integer)
    cap_age: Mapped[int | None] = mapped_column(Integer)
    conditions: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("field_evidence.id"))


# ---------------------------------------------------------------- users


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = _pk()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    firebase_uid: Mapped[str | None] = mapped_column(String(128), unique=True)
    consent_version: Mapped[str | None] = mapped_column(String(20))
    consent_at: Mapped[datetime | None] = mapped_column(DateTime)
    language: Mapped[str] = mapped_column(String(5), default="en")
    created_at: Mapped[datetime] = _created()
    last_seen_at: Mapped[datetime] = _created()


class UserProfile(Base):
    __tablename__ = "user_profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)  # date_of_birth, category, qualifications, ...
    purpose: Mapped[str] = mapped_column(String(200), default="eligibility matching and alerts")
    updated_at: Mapped[datetime] = _created()


class SavedExam(Base):
    __tablename__ = "saved_exams"
    __table_args__ = (UniqueConstraint("user_id", "exam_cycle_id"),)
    id: Mapped[int] = _pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    exam_cycle_id: Mapped[int] = mapped_column(ForeignKey("exam_cycles.id"))
    created_at: Mapped[datetime] = _created()


class UserExamStatus(Base):
    __tablename__ = "user_exam_status"
    __table_args__ = (UniqueConstraint("user_id", "exam_cycle_id"),)
    id: Mapped[int] = _pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    exam_cycle_id: Mapped[int] = mapped_column(ForeignKey("exam_cycles.id"))
    status: Mapped[str] = mapped_column(String(30))  # interested|applied|confirmed|admit_card|exam_taken|result_checked
    history: Mapped[list[Any] | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = _created()


class UserChecklistItem(Base):
    __tablename__ = "user_checklist_items"
    __table_args__ = (UniqueConstraint("user_id", "exam_cycle_id", "item_key"),)
    id: Mapped[int] = _pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    exam_cycle_id: Mapped[int] = mapped_column(ForeignKey("exam_cycles.id"))
    item_key: Mapped[str] = mapped_column(String(120))
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = _created()


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = _pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(20), default="android")
    fcm_token: Mapped[str | None] = mapped_column(String(500))
    app_version: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = _created()
    last_seen_at: Mapped[datetime] = _created()


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    enabled_types: Mapped[list[Any]] = mapped_column(JSON)
    interests: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # groups, sectors, organisations
    quiet_start: Mapped[str] = mapped_column(String(5), default="22:00")
    quiet_end: Mapped[str] = mapped_column(String(5), default="07:00")
    max_per_day: Mapped[int] = mapped_column(Integer, default=6)
    digest: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = _created()


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = _pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    deep_link: Mapped[str] = mapped_column(String(300))
    exam_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("exam_cycles.id"))
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    revision_id: Mapped[int | None] = mapped_column(ForeignKey("event_revisions.id"))
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|sent|bundled|suppressed|held
    bundle_key: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = _created()
    read_at: Mapped[datetime | None] = mapped_column(DateTime)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    id: Mapped[int] = _pk()
    notification_id: Mapped[int] = mapped_column(ForeignKey("notifications.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))
    channel: Mapped[str] = mapped_column(String(20), default="fcm")
    status: Mapped[str] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text)
    attempted_at: Mapped[datetime] = _created()


# ---------------------------------------------------------------- scam check and signals


class ScamCheck(Base):
    __tablename__ = "scam_checks"
    id: Mapped[int] = _pk()
    input_kind: Mapped[str] = mapped_column(String(10))  # url | text | pdf
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    submitted_text: Mapped[str | None] = mapped_column(Text)  # purged after retention window
    verdict: Mapped[str] = mapped_column(String(40))
    evidence: Mapped[list[Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = _created()
    purge_after: Mapped[datetime] = mapped_column(DateTime)


class FactCheckItem(Base):
    __tablename__ = "fact_check_items"
    id: Mapped[int] = _pk()
    source_url: Mapped[str] = mapped_column(String(1000))  # official PIB Fact Check post or official notice
    title: Mapped[str] = mapped_column(String(500))
    claim: Mapped[str | None] = mapped_column(Text)
    published_on: Mapped[date | None] = mapped_column(Date)
    keywords: Mapped[list[Any] | None] = mapped_column(JSON)
    urls: Mapped[list[Any] | None] = mapped_column(JSON)
    added_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = _created()


class NewsItem(Base):
    """Headlines from news publishers. Never treated as exam data; shown only as unverified mentions."""

    __tablename__ = "news_items"
    id: Mapped[int] = _pk()
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    guid: Mapped[str] = mapped_column(String(600), unique=True)
    title: Mapped[str] = mapped_column(String(600))
    url: Mapped[str] = mapped_column(String(1500))
    publisher: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    fetched_at: Mapped[datetime] = _created()
    organisation_id: Mapped[int | None] = mapped_column(ForeignKey("organisations.id"))
    matched_exam_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("exam_cycles.id"))
    public: Mapped[bool] = mapped_column(Boolean, default=True)


class MissedNoticeCandidate(Base):
    __tablename__ = "missed_notice_candidates"
    id: Mapped[int] = _pk()
    news_item_id: Mapped[int | None] = mapped_column(ForeignKey("news_items.id"))
    organisation_id: Mapped[int | None] = mapped_column(ForeignKey("organisations.id"))
    title: Mapped[str] = mapped_column(String(600))
    url: Mapped[str] = mapped_column(String(1500))
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|matched|confirmed|dismissed
    matched_source_item_id: Mapped[int | None] = mapped_column(ForeignKey("source_items.id"))
    created_at: Mapped[datetime] = _created()


# ---------------------------------------------------------------- admin


class AdminUser(Base):
    __tablename__ = "admin_users"
    id: Mapped[int] = _pk()
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    totp_secret: Mapped[str] = mapped_column(String(64))
    totp_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = _created()
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = _pk()
    actor: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(64))
    at: Mapped[datetime] = _created()
