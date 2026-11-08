"""Response and request models. These generate the OpenAPI spec that the Flutter client is built from."""

from datetime import date, datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class OrgOut(BaseModel):
    key: str
    name: str
    group: str
    collection: str


class EvidenceOut(BaseModel):
    quote: str
    page: int | None = None
    source_url: str
    document_hash: str | None = None
    retrieved_at: datetime | None = None
    published_on: date | None = None


class EventOut(BaseModel):
    id: int
    event_type: str
    title: str
    label: str | None = None
    date_start: date | None = None
    date_end: date | None = None
    precision: Literal["day", "month"] = "day"
    certainty: Literal["official", "tentative", "expected"]
    status: str
    category_number: str | None = None
    revision_count: int = 1
    is_deadline: bool = False
    evidence: EvidenceOut | None = None


class ExamSummary(BaseModel):
    id: int
    title: str
    exam_name: str
    organisation: OrgOut
    sector: str | None = None
    status: str
    is_fast_alert: bool
    next_event: EventOut | None = None
    application_end: EventOut | None = None
    exam_date: EventOut | None = None
    category_numbers: list[str] = []
    vacancies_total: int | None = None
    has_changes: bool = False
    official_url: str
    last_checked_at: datetime
    updated_at: datetime


class RuleOut(BaseModel):
    rule_type: str
    params: dict[str, Any]
    clause: str | None = None
    evidence: EvidenceOut | None = None


class PostOut(BaseModel):
    id: int
    name: str
    department: str | None = None
    vacancies: int | None = None
    vacancies_text: str | None = None
    pay_scale: str | None = None
    category_number: str | None = None
    rules: list[RuleOut] = []


class LinkOut(BaseModel):
    kind: str
    url: str
    label: str | None = None
    host: str


class ApplyOut(BaseModel):
    url: str
    host: str
    note: str | None = None
    copy_text: str | None = None
    copy_label: str | None = None


class FeeOut(BaseModel):
    amount: int
    categories: list[str] = []
    applies_to: str | None = None
    exempted: list[str] = []


class PhotoSpecOut(BaseModel):
    id: int
    item: str
    min_kb: int | None = None
    max_kb: int | None = None
    width: int | None = None
    height: int | None = None
    formats: list[str] = []
    evidence: EvidenceOut | None = None


class NewsOut(BaseModel):
    id: int
    title: str
    url: str
    publisher: str | None = None
    published_at: datetime | None = None
    organisation_key: str | None = None
    verified: bool = False
    label: str = "News report. Not verified by ExamRadar. Check the official website."


class ChangeOut(BaseModel):
    event_id: int
    event_title: str
    revision_no: int
    kind: str
    old_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    reason: str | None = None
    source_url: str | None = None
    created_at: datetime


class ExamDetail(ExamSummary):
    events: list[EventOut]
    posts: list[PostOut]
    links: list[LinkOut]
    apply: ApplyOut | None = None
    notification_pdf: str | None = None
    fees: list[FeeOut] = []
    qualification_text: str | None = None
    confirmation_notes: list[str] = []
    photo_specs: list[PhotoSpecOut] = []
    combined_with: list[str] = []
    changes: list[ChangeOut] = []
    news: list[NewsOut] = []
    summary: str | None = None
    summary_is_machine: bool = True
    source_status: str | None = None
    disclaimer: str


class CalendarEntry(BaseModel):
    date: date
    date_end: date | None = None
    exam_id: int
    exam_title: str
    organisation_key: str
    event_type: str
    title: str
    certainty: str
    precision: str
    is_deadline: bool


class NoticeOut(BaseModel):
    id: int
    title: str
    url: str | None
    kind: str
    organisation: OrgOut
    exam_id: int | None = None
    first_seen_at: datetime
    label: str = "New official notice detected"


class SourceStatusOut(BaseModel):
    key: str
    organisation: str | None
    url: str
    kind: str
    is_official: bool
    status: str
    collection: str | None = None
    last_success_at: datetime | None = None
    last_attempt_at: datetime | None = None
    last_new_item_at: datetime | None = None
    error_rate: float | None = None
    last_parser_yield: int | None = None
    note: str | None = None


class MetaOut(BaseModel):
    app_name: str
    disclaimer: str
    privacy_url: str
    api_version: str
    min_app_version: str
    organisations: list[OrgOut]
    qualifications: list[dict[str, Any]]
    kerala_communities: list[dict[str, Any]]
    central_categories: list[str]


class RegisterIn(BaseModel):
    platform: Literal["android", "ios", "web"] = "android"
    app_version: str | None = None
    fcm_token: str | None = Field(default=None, max_length=500)


class RegisterOut(BaseModel):
    token: str
    user_id: int


class DeviceIn(BaseModel):
    fcm_token: str | None = Field(default=None, max_length=500)
    app_version: str | None = None


class QualIn(BaseModel):
    code: str
    status: Literal["completed", "final_year", "appearing"] = "completed"
    percentage: float | None = Field(default=None, ge=0, le=100)


class ProfileData(BaseModel):
    date_of_birth: date | None = None
    category: Literal["GEN", "EWS", "OBC", "SC", "ST"] | None = None
    kerala_community: str | None = None
    pwd: bool | None = None
    ex_serviceman: bool | None = None
    gender: Literal["female", "male", "other"] | None = None
    nationality: str | None = None
    domicile_state: str | None = None
    qualifications: list[QualIn] = []
    languages: list[str] = []
    attempts: dict[str, int] = {}


class ProfileIn(BaseModel):
    consent: bool
    data: ProfileData


class ProfileOut(BaseModel):
    data: ProfileData | None
    consent_at: datetime | None = None
    purpose: str


class RuleResultOut(BaseModel):
    rule_type: str
    outcome: str
    user_value: str | None
    requirement: str
    explanation: str
    clause: str | None = None
    source_url: str | None = None
    page: int | None = None


class PostEligibility(BaseModel):
    post_id: int
    post_name: str
    status: Literal["eligible", "not_eligible", "needs_check"]
    results: list[RuleResultOut]


class ExamEligibility(BaseModel):
    exam_id: int
    exam_title: str
    status: Literal["eligible", "not_eligible", "needs_check"]
    posts: list[PostEligibility]
    countdown: list[dict[str, Any]] = []


class EvaluateIn(BaseModel):
    profile: ProfileData
    exam_ids: list[int] = Field(default=[], max_length=100)


class StatusIn(BaseModel):
    status: Literal["interested", "applied", "confirmed", "admit_card", "exam_taken", "result_checked"]


class MyExamOut(BaseModel):
    exam: ExamSummary
    status: str | None = None
    saved_at: datetime


class ChecklistItemOut(BaseModel):
    key: str
    text: str
    due: date | None = None
    certainty: str | None = None
    source_url: str | None = None
    done: bool = False


class CertificateRuleOut(BaseModel):
    certificate: str
    text: str
    issued_from: date | None = None
    issued_until: date | None = None
    financial_year: str | None = None
    valid_year: str | None = None
    evidence: EvidenceOut | None = None


class ChecklistOut(BaseModel):
    items: list[ChecklistItemOut]
    photo_specs: list[PhotoSpecOut]
    certificate_rules: list[CertificateRuleOut]
    note: str


class PrefsOut(BaseModel):
    enabled_types: list[str]
    interests: dict[str, list[str]]
    quiet_start: str
    quiet_end: str
    max_per_day: int
    digest: bool


class NotificationOut(BaseModel):
    id: int
    type: str
    title: str
    body: str
    deep_link: str
    exam_id: int | None
    urgent: bool
    created_at: datetime
    read: bool


class ScamIn(BaseModel):
    kind: Literal["url", "text"]
    value: str = Field(min_length=3, max_length=20000)


class ScamEvidenceOut(BaseModel):
    level: str
    text: str
    url: str | None = None


class ScamOut(BaseModel):
    id: int
    verdict: Literal["Verified on official source", "Not found on official sources", "Suspicious", "Known fake"]
    evidence: list[ScamEvidenceOut]
    disclaimer: str
