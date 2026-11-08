from datetime import date, timedelta

from examradar_core.models import CrawlRun, ExamCycle, NewsItem, Organisation, Source, SourceItem
from examradar_core.settings import get_settings
from examradar_eligibility import Profile
from examradar_eligibility.engine import taxonomy
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import schemas as S
from . import services as svc
from .deps import get_db, optional_user, today
from .scam import run_check

router = APIRouter(prefix="/v1", tags=["public"])


@router.get("/meta", response_model=S.MetaOut)
def meta(s: Session = Depends(get_db)) -> S.MetaOut:
    t = taxonomy()
    return S.MetaOut(app_name=get_settings().app_name, disclaimer=svc.DISCLAIMER, privacy_url=f"{get_settings().app_base_url}/privacy",
                     api_version="1.0", min_app_version="0.1.0",
                     organisations=[svc.org_out(o) for o in s.scalars(select(Organisation).order_by(Organisation.group, Organisation.name))],
                     qualifications=[{"code": q["code"], "name": q["name"], "level": q["level"]} for q in t["qualifications"]],
                     kerala_communities=t["kerala_communities"], central_categories=t["central_categories"])


@router.get("/exams", response_model=S.Page[S.ExamSummary])
def list_exams(q: str | None = Query(None, max_length=100), group: str | None = Query(None, pattern="^(central|kerala)$"),
               org: str | None = None, sector: str | None = None, status: str | None = None,
               date_from: date | None = None, date_to: date | None = None, ids: str | None = Query(None, max_length=2000),
               sort: str = Query("deadline", pattern="^(deadline|recent)$"), page: int = Query(1, ge=1),
               page_size: int = Query(20, ge=1, le=100), s: Session = Depends(get_db), d: date = Depends(today)):
    id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()] if ids else None
    return svc.search(s, d, q=q, group=group, org=org, sector=sector, status=status, date_from=date_from, date_to=date_to,
                      ids=id_list, page=page, page_size=page_size, sort=sort)


def _cycle(s: Session, exam_id: int) -> ExamCycle:
    c = s.get(ExamCycle, exam_id)
    if c is None or c.retracted:
        raise HTTPException(404, "Exam not found")
    return c


@router.get("/exams/{exam_id}", response_model=S.ExamDetail)
def exam_detail(exam_id: int, s: Session = Depends(get_db), d: date = Depends(today)):
    return svc.detail(s, _cycle(s, exam_id), d)


@router.get("/exams/{exam_id}/changes", response_model=list[S.ChangeOut])
def exam_changes(exam_id: int, s: Session = Depends(get_db), d: date = Depends(today)):
    return svc.detail(s, _cycle(s, exam_id), d).changes


@router.get("/exams/{exam_id}/posts", response_model=list[S.PostOut])
def exam_posts(exam_id: int, s: Session = Depends(get_db), d: date = Depends(today)):
    return svc.detail(s, _cycle(s, exam_id), d).posts


@router.get("/exams/{exam_id}/checklist", response_model=S.ChecklistOut)
def exam_checklist(exam_id: int, s: Session = Depends(get_db), d: date = Depends(today), user=Depends(optional_user)):
    return svc.checklist(s, _cycle(s, exam_id), d, user.id if user else None)


@router.get("/calendar", response_model=list[S.CalendarEntry])
def calendar(start: date, end: date, ids: str | None = Query(None, max_length=2000), s: Session = Depends(get_db)):
    if (end - start).days > 400 or end < start:
        raise HTTPException(422, "Choose a range of at most 400 days.")
    id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()] if ids else None
    return svc.calendar(s, start, end, id_list)


@router.get("/notices", response_model=S.Page[S.NoticeOut])
def notices(org: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=100), s: Session = Depends(get_db)):
    q = select(SourceItem).join(Source).where(Source.is_official.is_(True)).order_by(SourceItem.first_seen_at.desc())
    if org:
        q = q.join(Organisation, Source.organisation_id == Organisation.id).where(Organisation.key == org)
    rows = s.scalars(q.offset((page - 1) * page_size).limit(page_size + 1)).all()
    items = []
    for si in rows[:page_size]:
        src = s.get(Source, si.source_id)
        items.append(S.NoticeOut(id=si.id, title=si.title, url=si.url, kind=si.kind, organisation=svc.org_out(src.organisation),
                                 exam_id=si.exam_cycle_id, first_seen_at=si.first_seen_at))
    return S.Page[S.NoticeOut](items=items, total=(page - 1) * page_size + len(rows), page=page, page_size=page_size)


@router.get("/news", response_model=list[S.NewsOut])
def news(org: str | None = None, limit: int = Query(30, ge=1, le=100), s: Session = Depends(get_db)):
    """Headlines from news publishers. Shown as unverified mentions only; never used as exam data."""
    if not get_settings().news_mentions_public:
        return []
    recent = svc_now() - timedelta(days=90)  # feeds sometimes carry very old stories
    q = (select(NewsItem).where(NewsItem.public.is_(True), (NewsItem.published_at >= recent) | NewsItem.published_at.is_(None))
         .order_by(NewsItem.published_at.desc().nulls_last(), NewsItem.id.desc()))
    if org:
        q = q.join(Organisation, NewsItem.organisation_id == Organisation.id).where(Organisation.key == org)
    out = []
    for n in s.scalars(q.limit(limit)):
        o = s.get(Organisation, n.organisation_id) if n.organisation_id else None
        item = svc.news_out(n)
        item.organisation_key = o.key if o else None
        out.append(item)
    return out


@router.get("/sources", response_model=list[S.SourceStatusOut])
def sources(s: Session = Depends(get_db)):
    out = []
    for src in s.scalars(select(Source).order_by(Source.is_official.desc(), Source.key)):
        rate = (src.runs_failed / src.runs_total) if src.runs_total else None
        note = None
        if src.status == "manual":
            note = "Entered by our team from the official site, which cannot be read automatically."
        elif src.status == "blocked":
            note = "The site blocked automatic checks. Updates are entered manually until this is fixed."
        elif src.status == "stale":
            note = "Not checked recently. Information may be out of date."
        elif not src.is_official:
            note = "News publisher. Used only to spot notices early; not a source of exam data."
        out.append(S.SourceStatusOut(key=src.key, organisation=src.organisation.name if src.organisation else None, url=src.url,
                                     kind=src.kind, is_official=src.is_official, status=src.status,
                                     collection=src.organisation.collection if src.organisation else None,
                                     last_success_at=src.last_success_at, last_attempt_at=src.last_attempt_at,
                                     last_new_item_at=src.last_new_item_at, error_rate=round(rate, 3) if rate is not None else None,
                                     last_parser_yield=src.last_parser_yield, note=note))
    return out


@router.post("/eligibility/evaluate", response_model=list[S.ExamEligibility])
def evaluate_stateless(body: S.EvaluateIn, s: Session = Depends(get_db), d: date = Depends(today)):
    """Evaluates without storing the profile. Use this when the profile stays on the device."""
    profile = Profile.from_dict(body.profile.model_dump(mode="json"))
    ids = body.exam_ids or [r.id for r in svc.search(s, d, q=None, group=None, org=None, sector=None, status="open,upcoming",
                                                      date_from=None, date_to=None, ids=None, page=1, page_size=100).items]
    return [svc.eligibility(s, c, profile) for c in (s.get(ExamCycle, i) for i in ids) if c and not c.retracted]


@router.post("/scam-check", response_model=S.ScamOut)
def scam_check(body: S.ScamIn, s: Session = Depends(get_db)):
    return run_check(s, body.kind, body.value)


@router.post("/scam-check/pdf", response_model=S.ScamOut)
async def scam_check_pdf(file: UploadFile = File(...), s: Session = Depends(get_db)):
    data = await file.read(5_000_001)
    if len(data) > 5_000_000:
        raise HTTPException(413, "PDF is larger than 5 MB.")
    if not data.startswith(b"%PDF-"):
        raise HTTPException(422, "That file is not a PDF.")
    return run_check(s, "pdf", data)


@router.get("/stats/latency")
def detection_latency(s: Session = Depends(get_db)):
    """Median hours from the publication time stated in file names to our first detection, where that time is known."""
    rows = [(si.first_seen_at - si.published_hint).total_seconds() / 3600 for si in s.scalars(
        select(SourceItem).where(SourceItem.published_hint.is_not(None))) if si.first_seen_at >= si.published_hint]
    runs = s.scalars(select(CrawlRun).where(CrawlRun.started_at >= svc_now() - timedelta(days=7))).all()
    rows.sort()
    med = rows[len(rows) // 2] if rows else None
    return {"items_with_publication_time": len(rows), "median_hours": round(med, 2) if med is not None else None,
            "crawl_runs_7d": len(runs), "note": "Baseline items seen on the first crawl inflate this; see docs/evaluation.md."}


def svc_now():
    from examradar_core.timeutil import utcnow

    return utcnow()
