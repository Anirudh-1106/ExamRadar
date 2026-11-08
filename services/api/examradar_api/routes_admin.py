"""Server-rendered admin console (Jinja + HTMX). Every write needs a valid session, TOTP login, and CSRF token."""

import html
import json
import re
from datetime import date
from pathlib import Path

from examradar_core.models import (
    AuditLog,
    CrawlRun,
    Document,
    Event,
    ExamCycle,
    ExtractedField,
    FactCheckItem,
    FieldEvidence,
    MissedNoticeCandidate,
    Notification,
    Organisation,
    ReviewTask,
    Source,
)
from examradar_core.storage import get_store
from examradar_worker import jobs, ops
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import admin_auth as auth
from .deps import get_db

router = APIRouter(prefix="/admin", include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class NeedLogin(Exception):
    pass


def session(request: Request) -> dict:
    sess = auth.read_session(request.cookies.get(auth.SESSION_COOKIE))
    if sess is None:
        raise NeedLogin()
    return sess


def csrf_ok(request: Request, sess: dict, form_token: str | None) -> None:
    if not auth.check_csrf(sess, form_token or request.headers.get("x-csrf-token")):
        raise HTTPException(403, "Invalid CSRF token")


def page(request: Request, name: str, sess: dict | None, **ctx) -> HTMLResponse:
    return templates.TemplateResponse(request, name, {"sess": sess, "csrf": auth.csrf_token(sess) if sess else "", **ctx})


def ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return page(request, "login.html", None, error=None)


@router.post("/login")
def login_post(request: Request, email: str = Form(...), password: str = Form(...), code: str = Form(...), s: Session = Depends(get_db)):
    token, msg = auth.login(s, email, password, code.strip())
    if not token:
        s.commit()
        return page(request, "login.html", None, error=msg)
    ops.audit(s, email, "admin.login", "admin", None, ip=ip(request))
    r = RedirectResponse("/admin", status_code=303)
    r.set_cookie(auth.SESSION_COOKIE, token, max_age=auth.SESSION_MAX_AGE, httponly=True, samesite="strict",
                 secure=request.url.scheme == "https")
    return r


@router.post("/logout")
def logout():
    r = RedirectResponse("/admin/login", status_code=303)
    r.delete_cookie(auth.SESSION_COOKIE)
    return r


@router.get("", response_class=HTMLResponse)
def dashboard(request: Request, sess: dict = Depends(session), s: Session = Depends(get_db)):
    counts = {
        "open_reviews": s.scalar(select(func.count(ReviewTask.id)).where(ReviewTask.status == "open")),
        "urgent_reviews": s.scalar(select(func.count(ReviewTask.id)).where(ReviewTask.status == "open", ReviewTask.priority == 1)),
        "problem_sources": s.scalar(select(func.count(Source.id)).where(Source.status.in_(["failing", "blocked", "stale", "robots"]))),
        "missed": s.scalar(select(func.count(MissedNoticeCandidate.id)).where(MissedNoticeCandidate.status == "open")),
        "exams": s.scalar(select(func.count(ExamCycle.id))),
        "events": s.scalar(select(func.count(Event.id)).where(Event.status == "active")),
        "pending_notifications": s.scalar(select(func.count(Notification.id)).where(Notification.status.in_(["pending", "held"]))),
    }
    return page(request, "dashboard.html", sess, counts=counts)


@router.get("/review", response_class=HTMLResponse)
def review_list(request: Request, kind: str | None = None, sess: dict = Depends(session), s: Session = Depends(get_db)):
    q = select(ReviewTask).where(ReviewTask.status == "open").order_by(ReviewTask.priority, ReviewTask.created_at)
    if kind:
        q = q.where(ReviewTask.kind == kind)
    tasks = s.scalars(q.limit(200)).all()
    return page(request, "review_list.html", sess, tasks=tasks, kind=kind, cycles={t.id: s.get(ExamCycle, t.exam_cycle_id) for t in tasks})


def highlight(text: str, quote: str) -> str:
    """Escape the document text and wrap the evidence quote in <mark>, matching across whitespace."""
    esc = html.escape(text)
    parts = [p for p in quote.split(" | ")] if " | " in quote else [quote]
    for part in parts:
        words = [re.escape(html.escape(w)) for w in part.split()]
        if not words:
            continue
        rx = re.compile(r"\s*".join(words), re.I)
        esc = rx.sub(lambda m: f"<mark>{m.group(0)}</mark>", esc, count=1)
    return esc


@router.get("/review/{task_id}", response_class=HTMLResponse)
def review_detail(task_id: int, request: Request, sess: dict = Depends(session), s: Session = Depends(get_db)):
    t = s.get(ReviewTask, task_id)
    if t is None:
        raise HTTPException(404)
    ef = s.get(ExtractedField, t.extracted_field_id) if t.extracted_field_id else None
    ev = s.scalar(select(FieldEvidence).where(FieldEvidence.extracted_field_id == ef.id)) if ef else None
    doc = s.get(Document, ef.document_id) if ef else None
    page_text = ""
    if doc and doc.pages_text:
        idx = (ev.page or 1) - 1 if ev else 0
        page_text = doc.pages_text[min(max(idx, 0), len(doc.pages_text) - 1)]
    return page(request, "review_detail.html", sess, t=t, ef=ef, ev=ev, doc=doc, cycle=s.get(ExamCycle, t.exam_cycle_id) if t.exam_cycle_id else None,
                doc_html=highlight(page_text, ev.quote) if ev else html.escape(page_text), value_json=json.dumps(ef.value if ef else {}, indent=2, ensure_ascii=False),
                source=s.get(Source, t.source_id) if t.source_id else None)


@router.post("/review/{task_id}/approve")
def review_approve(task_id: int, request: Request, csrf: str = Form(None), edited: str = Form(""),
                   sess: dict = Depends(session), s: Session = Depends(get_db)):
    csrf_ok(request, sess, csrf)
    value = None
    if edited.strip():
        try:
            value = json.loads(edited)
        except json.JSONDecodeError as e:
            raise HTTPException(422, f"Edited value is not valid JSON: {e}") from e
    try:
        ops.approve_task(s, task_id, sess["email"], value, ip(request))
    except ops.OpError as e:
        raise HTTPException(409, str(e)) from e
    return _done(request, task_id, "Approved")


@router.post("/review/{task_id}/reject")
def review_reject(task_id: int, request: Request, csrf: str = Form(None), reason: str = Form("Incorrect extraction"),
                  sess: dict = Depends(session), s: Session = Depends(get_db)):
    csrf_ok(request, sess, csrf)
    try:
        ops.reject_task(s, task_id, sess["email"], reason, ip(request))
    except ops.OpError as e:
        raise HTTPException(409, str(e)) from e
    return _done(request, task_id, "Rejected")


def _done(request: Request, task_id: int, what: str) -> Response:
    if request.headers.get("hx-request"):
        return HTMLResponse(f'<tr><td colspan="6" class="muted">Task {task_id}: {what}.</td></tr>')
    return RedirectResponse("/admin/review", status_code=303)


@router.get("/documents/{doc_id}/raw")
def document_raw(doc_id: int, sess: dict = Depends(session), s: Session = Depends(get_db)):
    d = s.get(Document, doc_id)
    if d is None:
        raise HTTPException(404)
    ctype = "application/pdf" if d.storage_key.endswith(".pdf") else "text/plain; charset=utf-8"
    return Response(get_store().get(d.storage_key), media_type=ctype,
                    headers={"Content-Disposition": "inline", "Content-Security-Policy": "sandbox"})


@router.get("/sources", response_class=HTMLResponse)
def sources(request: Request, sess: dict = Depends(session), s: Session = Depends(get_db)):
    srcs = s.scalars(select(Source).order_by(Source.is_official.desc(), Source.key)).all()
    runs = s.scalars(select(CrawlRun).where(CrawlRun.status.in_(["failed", "blocked", "robots"])).order_by(CrawlRun.id.desc()).limit(30)).all()
    return page(request, "sources.html", sess, sources=srcs, runs=runs, names={x.id: x.key for x in srcs})


@router.post("/sources/{source_id}/recrawl")
def recrawl(source_id: int, request: Request, bg: BackgroundTasks, csrf: str = Form(None), sess: dict = Depends(session),
            s: Session = Depends(get_db)):
    csrf_ok(request, sess, csrf)
    src = s.get(Source, source_id)
    if src is None:
        raise HTTPException(404)
    ops.audit(s, sess["email"], "source.recrawl", "source", source_id, ip=ip(request))
    bg.add_task(jobs.crawl_source, source_id, True)
    bg.add_task(jobs.process_documents, 10)
    return HTMLResponse('<span class="muted">Queued. Refresh in a minute.</span>')


@router.get("/manual", response_class=HTMLResponse)
def manual_form(request: Request, exam_id: int | None = None, sess: dict = Depends(session), s: Session = Depends(get_db)):
    orgs = s.scalars(select(Organisation).order_by(Organisation.name)).all()
    return page(request, "manual.html", sess, orgs=orgs, exam=s.get(ExamCycle, exam_id) if exam_id else None, error=None, ok=None)


@router.post("/manual", response_class=HTMLResponse)
def manual_post(request: Request, csrf: str = Form(None), org_key: str = Form(...), exam_id: str = Form(""), exam_name: str = Form(""),
                cycle_title: str = Form(""), event_type: str = Form(...), date_start: date = Form(...), date_end: str = Form(""),
                certainty: str = Form("official"), source_url: str = Form(...), quote: str = Form(...),
                sess: dict = Depends(session), s: Session = Depends(get_db)):
    csrf_ok(request, sess, csrf)
    orgs = s.scalars(select(Organisation).order_by(Organisation.name)).all()
    try:
        e = ops.manual_event(s, sess["email"], cycle_id=int(exam_id) if exam_id.strip() else None, org_key=org_key,
                             exam_name=exam_name or None, cycle_title=cycle_title or None, event_type=event_type, date_start=date_start,
                             date_end=date.fromisoformat(date_end) if date_end else None, certainty=certainty,
                             source_url=source_url.strip(), quote=quote, ip=ip(request))
    except ops.OpError as err:
        return page(request, "manual.html", sess, orgs=orgs, exam=None, error=str(err), ok=None)
    return page(request, "manual.html", sess, orgs=orgs, exam=None, error=None, ok=f"Published event {e.id} on exam {e.exam_cycle_id}.")


@router.get("/exams/{exam_id}", response_class=HTMLResponse)
def exam_admin(exam_id: int, request: Request, sess: dict = Depends(session), s: Session = Depends(get_db)):
    c = s.get(ExamCycle, exam_id)
    if c is None:
        raise HTTPException(404)
    events = s.scalars(select(Event).where(Event.exam_cycle_id == c.id).order_by(Event.date_start)).all()
    return page(request, "exam.html", sess, c=c, events=events)


@router.get("/exams", response_class=HTMLResponse)
def exams(request: Request, q: str = "", sess: dict = Depends(session), s: Session = Depends(get_db)):
    stmt = select(ExamCycle).order_by(ExamCycle.updated_at.desc()).limit(100)
    if q:
        stmt = select(ExamCycle).where(ExamCycle.title.ilike(f"%{q}%")).order_by(ExamCycle.updated_at.desc()).limit(100)
    return page(request, "exams.html", sess, cycles=s.scalars(stmt).all(), q=q)


@router.post("/events/{event_id}/retract")
def retract(event_id: int, request: Request, csrf: str = Form(None), reason: str = Form(...), sess: dict = Depends(session),
            s: Session = Depends(get_db)):
    csrf_ok(request, sess, csrf)
    if len(reason.strip()) < 5:
        raise HTTPException(422, "Give a reason users will see.")
    try:
        ev = s.get(Event, event_id)
        ops.retract_event(s, event_id, sess["email"], reason.strip(), ip(request))
    except ops.OpError as e:
        raise HTTPException(409, str(e)) from e
    return RedirectResponse(f"/admin/exams/{ev.exam_cycle_id}", status_code=303)


@router.post("/exams/{exam_id}/retract")
def retract_exam(exam_id: int, request: Request, csrf: str = Form(None), reason: str = Form(...), sess: dict = Depends(session),
                 s: Session = Depends(get_db)):
    csrf_ok(request, sess, csrf)
    ops.retract_cycle(s, exam_id, sess["email"], reason.strip(), ip(request))
    return RedirectResponse(f"/admin/exams/{exam_id}", status_code=303)


@router.get("/missed", response_class=HTMLResponse)
def missed(request: Request, sess: dict = Depends(session), s: Session = Depends(get_db)):
    rows = s.scalars(select(MissedNoticeCandidate).where(MissedNoticeCandidate.status == "open").order_by(MissedNoticeCandidate.id.desc()).limit(200)).all()
    return page(request, "missed.html", sess, rows=rows, orgs={o.id: o for o in s.scalars(select(Organisation))})


@router.post("/missed/{cand_id}/{action}")
def missed_action(cand_id: int, action: str, request: Request, csrf: str = Form(None), sess: dict = Depends(session),
                  s: Session = Depends(get_db)):
    csrf_ok(request, sess, csrf)
    c = s.get(MissedNoticeCandidate, cand_id)
    if c is None or action not in ("dismiss", "confirm"):
        raise HTTPException(404)
    c.status = "dismissed" if action == "dismiss" else "confirmed"
    ops.audit(s, sess["email"], f"missed.{action}", "missed_notice", cand_id, ip=ip(request))
    return HTMLResponse(f'<tr><td colspan="4" class="muted">{c.status.title()}.</td></tr>')


@router.get("/factcheck", response_class=HTMLResponse)
def factcheck(request: Request, sess: dict = Depends(session), s: Session = Depends(get_db)):
    return page(request, "factcheck.html", sess, rows=s.scalars(select(FactCheckItem).order_by(FactCheckItem.id.desc())).all(), error=None)


@router.post("/factcheck", response_class=HTMLResponse)
def factcheck_post(request: Request, csrf: str = Form(None), source_url: str = Form(...), title: str = Form(...), claim: str = Form(""),
                   keywords: str = Form(""), urls: str = Form(""), sess: dict = Depends(session), s: Session = Depends(get_db)):
    csrf_ok(request, sess, csrf)
    host = re.sub(r"^https?://", "", source_url).split("/")[0].lower()
    if host not in ("pib.gov.in", "www.pib.gov.in", "x.com", "twitter.com") and not host.endswith(".gov.in"):
        rows = s.scalars(select(FactCheckItem).order_by(FactCheckItem.id.desc())).all()
        return page(request, "factcheck.html", sess, rows=rows, error="The source must be PIB Fact Check or an official .gov.in notice.")
    s.add(FactCheckItem(source_url=source_url, title=title, claim=claim or None, added_by=sess["email"],
                        keywords=[k.strip() for k in keywords.split(",") if k.strip()] or None,
                        urls=[u.strip() for u in urls.split() if u.strip()] or None))
    ops.audit(s, sess["email"], "factcheck.add", "fact_check", None, after={"title": title, "source": source_url}, ip=ip(request))
    return RedirectResponse("/admin/factcheck", status_code=303)


@router.get("/notifications", response_class=HTMLResponse)
def notifications(request: Request, sess: dict = Depends(session), s: Session = Depends(get_db)):
    pending = s.scalars(select(Notification).where(Notification.status.in_(["pending", "held"])).order_by(Notification.id.desc()).limit(100)).all()
    recent = s.scalars(select(Notification).where(Notification.status.in_(["sent", "bundled"])).order_by(Notification.id.desc()).limit(50)).all()
    return page(request, "notifications.html", sess, pending=pending, recent=recent)


@router.get("/audit", response_class=HTMLResponse)
def audit_log(request: Request, sess: dict = Depends(session), s: Session = Depends(get_db)):
    return page(request, "audit.html", sess, rows=s.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(300)).all())
