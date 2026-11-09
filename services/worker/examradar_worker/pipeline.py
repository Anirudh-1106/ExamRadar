"""The update pipeline: schedule -> fetch -> store original -> detect -> fast alert -> extract -> validate ->
publish or review -> revise -> notify. Each stage is a method so tests and the admin console can call it directly."""

import hashlib
import json
import logging
import re
from dataclasses import asdict
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from examradar_adapters.base import Adapter, CycleHint, Fact, Item, Listing
from examradar_adapters.http import FetchError, PoliteClient, RobotsDisallowed, SourceBlocked
from examradar_adapters.news import parse_feed
from examradar_adapters.normalise import main_text, text_hash
from examradar_adapters.registry import build_adapter, load_config
from examradar_core.enums import EVENT_TYPES
from examradar_core.models import (
    CategoryNumber,
    CrawlRun,
    Document,
    EligibilityRule,
    Event,
    EventRevision,
    Exam,
    ExamCategoryLink,
    ExamCycle,
    ExtractedField,
    ExtractionRun,
    FieldEvidence,
    Link,
    MissedNoticeCandidate,
    NewsItem,
    OfficialDomain,
    Organisation,
    Post,
    ReviewTask,
    Source,
    SourceItem,
    SourceSnapshot,
)
from examradar_core.settings import get_settings
from examradar_core.storage import content_key, get_store, sha256
from examradar_core.timeutil import ist_today, utcnow
from examradar_extraction.llm import LLMProvider, llm_facts
from examradar_extraction.pdf import extract_html, extract_pdf
from examradar_extraction.validate import (
    AUTO_PUBLISH_CONFIDENCE,
    check_event_date,
    check_ordering,
    link_allowed,
    verify_quote,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import notify

log = logging.getLogger(__name__)
RULES_VERSION = "2026.11.1"
PLACEHOLDER = re.compile(r"^(KDRB )?Category \d", re.I)


def _stopless(s: str) -> set[str]:
    stop = {"the", "and", "for", "with", "out", "check", "here", "how", "2025", "2026", "2027", "exam", "result", "notification"}
    return {t for t in re.findall(r"[a-z0-9]{3,}", s.lower()) if t not in stop}


class Pipeline:
    def __init__(self, s: Session, client: PoliteClient | None = None, today: date | None = None,
                 llm: LLMProvider | None = None, max_follow: int = 30, max_docs: int = 20, notify_enabled: bool = True,
                 force: bool = False):
        self.s = s
        self.client = client or PoliteClient()
        self.today = today or ist_today()
        self.llm = llm
        self.follow_budget = max_follow
        self.max_docs = max_docs
        self.notify_enabled = notify_enabled
        self.force = force
        self.cfg = {o["key"]: o for o in load_config()["organisations"]}
        self._adapters: dict[str, Adapter] = {}
        self._domains: dict[int, list[dict[str, Any]]] = {}
        self.baseline = False
        for o in self.cfg.values():
            if o.get("crawl_delay_seconds"):
                for d in o.get("domains", []):
                    self.client.set_host_delay(d["host"], float(o["crawl_delay_seconds"]))

    # ------------------------------------------------------------------ helpers
    def adapter(self, org_key: str) -> Adapter:
        if org_key not in self._adapters:
            self._adapters[org_key] = build_adapter(self.cfg[org_key])
        return self._adapters[org_key]

    def domains(self, org_id: int) -> list[dict[str, Any]]:
        if org_id not in self._domains:
            self._domains[org_id] = [{"host": d.host, "path_prefix": d.path_prefix, "purpose": d.purpose}
                                     for d in self.s.scalars(select(OfficialDomain).where(OfficialDomain.organisation_id == org_id))]
        return self._domains[org_id]

    def content_host_ok(self, org: Organisation, url: str) -> bool:
        return link_allowed(url, self.domains(org.id), ("content",))

    def review(self, kind: str, reason: str, *, field: ExtractedField | None = None, cycle: ExamCycle | None = None,
               source: Source | None = None, payload: dict | None = None, priority: int = 2) -> ReviewTask:
        t = ReviewTask(kind=kind, reason=reason, extracted_field_id=field.id if field else None,
                       exam_cycle_id=cycle.id if cycle else None, source_id=source.id if source else None,
                       payload=payload, priority=priority)
        self.s.add(t)
        self.s.flush()
        return t

    def store_document(self, org: Organisation | None, url: str, data: bytes, ctype: str, kind: str,
                       title: str | None = None, pages: list[str] | None = None) -> tuple[Document, bool]:
        digest = sha256(data)
        doc = self.s.scalar(select(Document).where(Document.url == url, Document.sha256 == digest))
        now = utcnow()
        if doc:
            doc.last_checked_at = now
            return doc, False
        ext = ".pdf" if "pdf" in ctype or url.lower().endswith(".pdf") else (".xml" if "xml" in ctype else ".html")
        key = content_key(digest, ext)
        store = get_store()
        if not store.exists(key):
            store.put(key, data, ctype or "application/octet-stream")
        doc = Document(organisation_id=org.id if org else None, url=url, sha256=digest, storage_key=key,
                       content_type=ctype or "", size=len(data), title=title, kind=kind,
                       text="\n".join(pages) if pages else None, pages_text=pages, page_count=len(pages) if pages else None)
        self.s.add(doc)
        self.s.flush()
        return doc, True

    # ------------------------------------------------------------------ crawl
    def run_source(self, src: Source) -> CrawlRun | None:
        if src.kind == "news":
            return self.run_news(src)
        if src.kind == "manual" or not src.enabled:
            return None
        org = src.organisation
        ad = self.adapter(org.key)
        run = CrawlRun(source_id=src.id)
        self.s.add(run)
        src.last_attempt_at = utcnow()
        src.runs_total += 1
        self.s.flush()
        try:
            res = ad.fetch(self.client, src.url, None if self.force else src.etag, None if self.force else src.last_modified)
        except SourceBlocked as e:
            return self._fail(src, run, "blocked", str(e))
        except RobotsDisallowed as e:
            return self._fail(src, run, "robots", str(e))
        except FetchError as e:
            return self._fail(src, run, "failed", str(e))
        run.http_status = res.status
        run.bytes = len(res.content)
        if res.not_modified:
            run.status = "unchanged"
            return self._ok(src, run)
        is_xml = "xml" in res.content_type or src.kind == "rss"
        text = res.content.decode("utf-8", "ignore") if is_xml else main_text(res.content)
        nh = text_hash(text)
        snap_doc, _ = self.store_document(org, res.final_url, res.content, res.content_type, "listing",
                                          f"Listing page {src.url}", [text])
        self.s.add(SourceSnapshot(source_id=src.id, crawl_run_id=run.id, url=res.final_url, http_status=res.status,
                                  content_type=res.content_type, raw_hash=sha256(res.content), normalized_hash=nh,
                                  storage_key=snap_doc.storage_key, normalized_text=text[:200000]))
        self.baseline = src.last_success_at is None
        if nh == src.last_hash and not self.force:
            run.status = "unchanged"
            return self._ok(src, run)
        items = ad.parse_listing(Listing(src.url, src.kind), res.content, res.final_url)
        prev = src.last_parser_yield
        src.last_parser_yield = len(items)
        run.items_found = len(items)
        if not items and prev:
            self.review("source_health", f"{src.key}: parser found no items (was {prev}). The page layout may have changed.",
                        source=src, priority=1)
        new = 0
        for it in items:
            new += self.ingest_item(src, org, ad, it, snap_doc)
        run.new_items = new
        src.last_hash, src.etag, src.last_modified = nh, res.etag, res.last_modified
        if new:
            src.last_new_item_at = utcnow()
        run.status = "ok"
        return self._ok(src, run)

    def _ok(self, src: Source, run: CrawlRun) -> CrawlRun:
        now = utcnow()
        src.last_success_at, src.consecutive_failures, src.status, src.last_error = now, 0, "ok", None
        run.finished_at = now
        if run.status == "running":
            run.status = "ok"
        self.s.flush()
        return run

    def _fail(self, src: Source, run: CrawlRun, status: str, err: str) -> CrawlRun:
        run.status, run.error, run.finished_at = status, err[:2000], utcnow()
        src.runs_failed += 1
        src.consecutive_failures += 1
        src.last_error = err[:2000]
        if status in ("blocked", "robots"):
            src.status = status
            self.review("source_health", f"{src.key}: {status}. {err[:300]} Use manual entry until resolved.", source=src, priority=1)
        elif src.consecutive_failures >= 3:
            src.status = "failing"
            if src.consecutive_failures == 3:
                self.review("source_health", f"{src.key}: 3 consecutive failures. Last error: {err[:300]}", source=src, priority=1)
        self.s.flush()
        return run

    # ------------------------------------------------------------------ items
    def ingest_item(self, src: Source, org: Organisation, ad: Adapter, item: Item, evidence_doc: Document,
                    depth: int = 0) -> int:
        si = self.s.scalar(select(SourceItem).where(SourceItem.source_id == src.id, SourceItem.item_key == item.key[:500]))
        chash = hashlib.sha256(json.dumps([item.title, item.doc_urls, [(f.field, f.value) for f in item.facts]],
                                          sort_keys=True, default=str).encode()).hexdigest()
        is_new = si is None
        if is_new:
            si = SourceItem(source_id=src.id, item_key=item.key[:500], title=item.title, url=item.url)
            self.s.add(si)
            self.s.flush()
        else:
            si.last_seen_at = utcnow()
            if si.content_hash == chash and not self.force:
                return 0
        si.content_hash = chash
        si.title, si.url, si.kind = item.title, item.url, ad.classify(item)
        si.published_hint = item.published_hint
        si.data = {"doc_urls": item.doc_urls, "cycle": asdict(item.cycle) if item.cycle else None, "data": item.data}
        cycle = self.cycle_from_hint(org, item.cycle, item.url or src.url) if item.cycle else None
        if cycle:
            si.exam_cycle_id = cycle.id
            if item.url and self.content_host_ok(org, item.url):
                self.upsert_link(cycle, item.url, "notification" if si.kind == "notification" else "official_page", item.title[:300], org)
        if depth == 0:
            for url in item.follow[:1]:
                if not self.content_host_ok(org, url):
                    continue
                if self.follow_budget <= 0:
                    break
                self.follow_budget -= 1
                try:
                    res = self.client.get(url)
                except FetchError as e:
                    log.warning("follow failed", extra={"data": {"url": url, "error": str(e)[:200]}})
                    continue
                ddoc, _ = self.store_document(org, res.final_url, res.content, res.content_type, "detail", item.title[:300],
                                              [main_text(res.content)])
                for ch in ad.parse_detail(url, res.content):
                    if ch.cycle is None and item.cycle is not None:
                        ch.cycle = item.cycle
                    self.ingest_item(src, org, ad, ch, ddoc, depth + 1)
        if item.facts:
            self.apply_facts(org, ad, cycle, item.facts, evidence_doc)
        si.processed = not (item.doc_urls and item.data.get("fetch", True))
        if is_new and not self.baseline and src.is_official and self.notify_enabled:
            notify.on_new_notice(self.s, cycle, org.key, org.group, item.title, si.id)
            si.fast_alert_sent = True
        self.s.flush()
        return 1 if is_new else 0

    # ------------------------------------------------------------------ cycles
    def cycle_from_hint(self, org: Organisation, hint: CycleHint, url: str | None) -> ExamCycle:
        exam = self.s.scalar(select(Exam).where(Exam.slug == hint.exam_slug))
        if exam is None:
            exam = Exam(organisation_id=org.id, slug=hint.exam_slug, name=hint.exam_name, sector=hint.sector)
            self.s.add(exam)
            self.s.flush()
        cycle = None
        for cat in hint.category_numbers:
            cn = self.s.scalar(select(CategoryNumber).where(CategoryNumber.organisation_id == org.id, CategoryNumber.number == cat))
            if cn and cn.exam_cycle_id:
                cycle = self.s.get(ExamCycle, cn.exam_cycle_id)
                break
        if cycle is None:
            q = select(ExamCycle).where(ExamCycle.exam_id == exam.id)
            q = q.where(ExamCycle.notification_number == hint.notification_number) if hint.notification_number else q.where(ExamCycle.title == hint.title)
            cycle = self.s.scalar(q)
        if cycle is None:
            cycle = ExamCycle(exam_id=exam.id, title=hint.title[:600], year=hint.year, notification_number=hint.notification_number,
                              official_url=url or "", is_fast_alert=True)
            self.s.add(cycle)
            self.s.flush()
        elif PLACEHOLDER.match(cycle.title) and not PLACEHOLDER.match(hint.title):
            cycle.title, cycle.exam_id = hint.title[:600], exam.id
        for cat in hint.category_numbers:
            cn = self.s.scalar(select(CategoryNumber).where(CategoryNumber.organisation_id == org.id, CategoryNumber.number == cat))
            if cn is None:
                cn = CategoryNumber(organisation_id=org.id, number=cat, year=int(cat[-4:]), post_title=hint.exam_name)
                self.s.add(cn)
            if cn.exam_cycle_id is None:
                cn.exam_cycle_id = cycle.id
        self.s.flush()
        return cycle

    def cycle_for_category(self, org: Organisation, ad: Adapter, cat: str, post: str | None, dept: str | None) -> ExamCycle | None:
        cn = self.s.scalar(select(CategoryNumber).where(CategoryNumber.organisation_id == org.id, CategoryNumber.number == cat))
        if cn and cn.exam_cycle_id:
            return self.s.get(ExamCycle, cn.exam_cycle_id)
        hint = ad.cycle_for_category(cat, post, dept)
        return self.cycle_from_hint(org, hint, None) if hint else None

    def upsert_link(self, cycle: ExamCycle, url: str, kind: str, label: str | None, org: Organisation) -> Link | None:
        allowed = link_allowed(url, self.domains(org.id))
        if not allowed:
            return None
        link = self.s.scalar(select(Link).where(Link.exam_cycle_id == cycle.id, Link.url == url))
        if link is None:
            previous = self.s.scalar(select(Link).where(Link.exam_cycle_id == cycle.id, Link.kind == "apply")) if kind == "apply" else None
            link = Link(exam_cycle_id=cycle.id, kind=kind, url=url, label=label, host=urlparse(url).hostname or "", allowlisted=True)
            self.s.add(link)
            self.s.flush()
            if kind in ("notification", "official_page") and not cycle.official_url:
                cycle.official_url = url
            if previous is not None and self.notify_enabled:
                notify.on_link_changed(self.s, cycle, link)
        return link

    # ------------------------------------------------------------------ documents
    def process_documents(self, limit: int | None = None) -> int:
        limit = limit or self.max_docs
        q = (select(SourceItem).where(SourceItem.processed.is_(False)).order_by(SourceItem.published_hint.desc().nulls_last(),
                                                                              SourceItem.first_seen_at.desc()).limit(limit))
        done = 0
        for si in self.s.scalars(q).all():
            src = self.s.get(Source, si.source_id)
            org = src.organisation
            ad = self.adapter(org.key)
            payload = si.data or {}
            item = Item(key=si.item_key, title=si.title, url=si.url, kind=si.kind, doc_urls=payload.get("doc_urls", []),
                        cycle=CycleHint(**payload["cycle"]) if payload.get("cycle") else None, data=payload.get("data") or {},
                        published_hint=si.published_hint)
            cycle = self.s.get(ExamCycle, si.exam_cycle_id) if si.exam_cycle_id else None
            for url in item.doc_urls[:2]:
                if not self.content_host_ok(org, url):
                    continue
                try:
                    res = self.client.get(url)
                except FetchError as e:
                    si.data = {**payload, "doc_error": str(e)[:300]}
                    continue
                doc, fresh = self.store_document(org, res.final_url, res.content, res.content_type, si.kind, si.title[:500])
                if not fresh and doc.processed_at:
                    continue
                self.process_document(org, ad, item, cycle, doc, res.content)
                si.document_id = doc.id
                done += 1
            si.processed = True
            # Commit per document so a long run never holds the database and finished work survives interruptions.
            self.s.commit()
        return done

    def process_document(self, org: Organisation, ad: Adapter, item: Item, cycle: ExamCycle | None, doc: Document,
                         data: bytes) -> list[Fact]:
        is_pdf = data[:5] == b"%PDF-"
        dt = extract_pdf(data, **ad.doc_options(item)) if is_pdf else extract_html(data)
        doc.text, doc.pages_text, doc.page_count = dt.text, dt.pages, len(dt.pages)
        doc.text_quality, doc.ocr_used, doc.language = dt.quality, dt.ocr_used, dt.language
        if item.published_hint:
            doc.published_on = item.published_hint.date()
        facts = ad.extract(item, dt)
        critical = {"application_end", "exam"}
        if item.kind == "notification" and not any(f.field == "event" and f.value.get("event_type") in critical for f in facts):
            facts += llm_facts(dt.text, {"application_start", "application_end", "exam"}, self.llm)
        if dt.quality < 0.5:
            self.review("field", f"Low text quality ({dt.quality}) in {doc.url}. Check extracted values or enter manually.",
                        cycle=cycle, payload={"document_id": doc.id}, priority=2)
        self.apply_facts(org, ad, cycle, facts, doc)
        doc.processed_at = utcnow()
        self.s.flush()
        return facts

    # ------------------------------------------------------------------ facts
    def apply_facts(self, org: Organisation, ad: Adapter, cycle: ExamCycle | None, facts: list[Fact], doc: Document) -> None:
        if not facts:
            return
        run = ExtractionRun(document_id=doc.id, extractor=ad.key, version=RULES_VERSION,
                            llm_used=any(f.method == "llm" for f in facts), finished_at=utcnow())
        self.s.add(run)
        self.s.flush()
        pages = doc.pages_text or [doc.text or ""]
        org_rules = False
        if any(f.field in ("relaxation", "relaxation_cap") for f in facts):
            # Re-reading the same General Conditions replaces its earlier facts instead of adding duplicates.
            for old in self.s.scalars(select(ExtractedField).where(ExtractedField.document_id == doc.id, ExtractedField.status == "published",
                                                                  ExtractedField.field_name.in_(["relaxation", "relaxation_cap"]))):
                old.status = "superseded"
        for f in facts:
            ef = ExtractedField(extraction_run_id=run.id, document_id=doc.id, field_name=f.field, value=f.value,
                                confidence=f.confidence, method=f.method)
            self.s.add(ef)
            self.s.flush()
            qm = verify_quote(f.quote, pages)
            if not qm.ok:
                ef.status, ef.validation_errors = "rejected", ["supporting quote not found in the stored document text"]
                continue
            ev = FieldEvidence(extracted_field_id=ef.id, document_id=doc.id, document_hash=doc.sha256, source_url=doc.url,
                               page=f.page or qm.page, quote=f.quote[:4000], char_start=qm.start, char_end=qm.end,
                               published_on=doc.published_on, retrieved_at=doc.retrieved_at, last_checked_at=doc.last_checked_at)
            self.s.add(ev)
            self.s.flush()
            if f.field in ("relaxation", "relaxation_cap"):
                # Organisation-wide rules (Kerala PSC General Conditions) apply to every post that refers to them.
                ef.status = "published" if f.confidence >= AUTO_PUBLISH_CONFIDENCE else "needs_review"
                org_rules = True
                continue
            for target, cat in self.targets(org, ad, cycle, f):
                ef.exam_cycle_id = ef.exam_cycle_id or target.id
                self.apply_one(org, target, cat, f.field, f.value, ef, ev, doc, f.method, f.confidence)
            if ef.exam_cycle_id is None and ef.status == "candidate":
                ef.status = "unassigned"
        self.s.flush()
        if org_rules:
            self.apply_org_relaxations(org)

    def targets(self, org: Organisation, ad: Adapter, cycle: ExamCycle | None, f: Fact) -> list[tuple[ExamCycle, str | None]]:
        cats = f.value.get("category_numbers") or []
        if cats:
            out = []
            for c in cats:
                t = self.cycle_for_category(org, ad, c, f.value.get("post"), f.value.get("department"))
                if t:
                    out.append((t, c))
            if len(cats) > 1 and f.field == "event" and f.value.get("event_type") == "exam" and out:
                self._link_combined(out)
            return out
        if f.value.get("cycle"):
            return [(self.cycle_from_hint(org, CycleHint(**f.value["cycle"]), None), None)]
        return [(cycle, None)] if cycle else []

    def _link_combined(self, targets: list[tuple[ExamCycle, str | None]]) -> None:
        """One programme row listing several category numbers is a common exam; link them together."""
        anchor = targets[0][0]
        for t, cat in targets:
            cn = self.s.scalar(select(CategoryNumber).where(CategoryNumber.number == cat, CategoryNumber.exam_cycle_id == t.id))
            if cn and not self.s.scalar(select(ExamCategoryLink).where(ExamCategoryLink.exam_cycle_id == anchor.id,
                                                                     ExamCategoryLink.category_number_id == cn.id)):
                self.s.add(ExamCategoryLink(exam_cycle_id=anchor.id, category_number_id=cn.id))

    def apply_one(self, org: Organisation, cycle: ExamCycle, cat: str | None, field: str, v: dict[str, Any],
                  ef: ExtractedField, ev: FieldEvidence, doc: Document, method: str, conf: float, *,
                  force: bool = False, actor: str = "pipeline", reason: str | None = None) -> None:
        auto = force or (method != "llm" and conf >= AUTO_PUBLISH_CONFIDENCE)
        cycle.last_checked_at = utcnow()
        if field == "event":
            self._apply_event(cycle, cat, v, ef, ev, doc, auto, force, actor, reason)
        elif field == "link":
            if not link_allowed(v["url"], self.domains(org.id)):
                ef.status, ef.validation_errors = "needs_review", ["link host is not on this organisation's allowlist"]
                self.review("field", f"Link not on allowlist: {v['url']}", field=ef, cycle=cycle, priority=2)
                return
            link = self.upsert_link(cycle, v["url"], v.get("kind", "apply"), v.get("label"), org)
            if link:
                link.kind = v.get("kind", link.kind)
            ef.status = "published"
        elif field == "post":
            if not auto:
                return self._to_review(ef, cycle, f"Post details need review ({conf:.2f})")
            post = self.s.scalar(select(Post).where(Post.exam_cycle_id == cycle.id, Post.name == v["name"][:500]))
            if post is None:
                post = Post(exam_cycle_id=cycle.id, name=v["name"][:500])
                self.s.add(post)
            post.department, post.pay_scale = v.get("department"), v.get("pay_scale")
            post.vacancies, post.vacancies_text = v.get("vacancies"), v.get("vacancies_text")
            if cat:
                cn = self.s.scalar(select(CategoryNumber).where(CategoryNumber.organisation_id == org.id, CategoryNumber.number == cat))
                if cn:
                    post.category_number_id = cn.id
            ef.status = "published"
        elif field == "vacancies":
            if not auto:
                return self._to_review(ef, cycle, "Vacancy count needs review")
            cycle.vacancies_total = v["total"]
            ef.status = "published"
        elif field == "fee":
            if not auto:
                return self._to_review(ef, cycle, "Fee needs review")
            cycle.fee_summary = (cycle.fee_summary or []) + [{**v, "evidence_id": ev.id}]
            ef.status = "published"
        elif field in ("age_rule", "relaxation_reference", "qualification"):
            if not auto:
                return self._to_review(ef, cycle, f"{field} needs review")
            rule_type = {"age_rule": "age", "relaxation_reference": "relaxation_reference", "qualification": "qualification_text"}[field]
            if field == "qualification":
                cycle.qualification_text = v["text"]
            posts = self.s.scalars(select(Post).where(Post.exam_cycle_id == cycle.id)).all()
            if not posts:
                posts = [Post(exam_cycle_id=cycle.id, name=cycle.exam.name[:500])]
                self.s.add(posts[0])
                self.s.flush()
            for p in posts:
                for old in self.s.scalars(select(EligibilityRule).where(EligibilityRule.post_id == p.id,
                                                                      EligibilityRule.rule_type == rule_type)):
                    old.status = "superseded"
                self.s.add(EligibilityRule(post_id=p.id, rule_type=rule_type, params=v, clause_text=ev.quote, evidence_id=ev.id))
            ef.status = "published"
            if field == "relaxation_reference":
                self.s.flush()
                self.apply_org_relaxations(org, cycle)
            if field == "age_rule" and self.notify_enabled:
                self.s.flush()
                notify.on_new_matching_exam(self.s, cycle, self.today)
        elif field == "notification_number":
            if not cycle.notification_number:
                cycle.notification_number = v["number"]
            elif v["number"] not in cycle.notification_number:
                # The document names another number than the listing gave this exam: another category of a
                # multi-category notice, or an older notification cited on the first page. The listing number stays.
                ef.status, ef.validation_errors = "rejected", [f"number {v['number']} differs from {cycle.notification_number}"]
                return
            ef.status = "published"
        elif field == "confirmation_note":
            ef.status = "published"
        elif field == "certificate_rule":
            if not auto:
                return self._to_review(ef, cycle, "Certificate rule needs review")
            ef.status = "published"
        else:  # photo_spec and anything new: humans decide
            if force:
                ef.status = "published"
            else:
                self._to_review(ef, cycle, f"{field} needs review before it is used on devices")
        self.s.flush()

    def apply_org_relaxations(self, org: Organisation, cycle: ExamCycle | None = None) -> int:
        """Attach the organisation's published age relaxations to posts whose notification refers to them."""
        latest_doc = self.s.scalar(
            select(func.max(ExtractedField.document_id)).join(Document, Document.id == ExtractedField.document_id).where(
                Document.organisation_id == org.id, ExtractedField.field_name == "relaxation", ExtractedField.status == "published"))
        if latest_doc is None:
            return 0
        fields = self.s.scalars(select(ExtractedField).where(ExtractedField.document_id == latest_doc, ExtractedField.status == "published",
                                                            ExtractedField.field_name.in_(["relaxation", "relaxation_cap"]))).all()
        cap = next((f.value["cap_age"] for f in fields if f.field_name == "relaxation_cap"), None)
        rels = [f for f in fields if f.field_name == "relaxation"]
        q = (select(EligibilityRule).join(Post, Post.id == EligibilityRule.post_id).join(ExamCycle, ExamCycle.id == Post.exam_cycle_id)
             .join(Exam, Exam.id == ExamCycle.exam_id).where(Exam.organisation_id == org.id, EligibilityRule.rule_type == "relaxation_reference",
                                                             EligibilityRule.status == "published"))
        if cycle is not None:
            q = q.where(ExamCycle.id == cycle.id)
        n = 0
        for ref in self.s.scalars(q).all():
            for old in self.s.scalars(select(EligibilityRule).where(EligibilityRule.post_id == ref.post_id, EligibilityRule.rule_type == "relaxation",
                                                                  EligibilityRule.status == "published")):
                old.status = "superseded"
            # Only the General Conditions paragraphs this notification applies, minus any already built into its limit.
            allowed = set(ref.params.get("paras") or []) or None
            excluded = set(ref.params.get("exclude") or [])
            for f in rels:
                para = f.value.get("para")
                if para and ((allowed is not None and para not in allowed) or para in excluded):
                    continue
                ev = self.s.scalar(select(FieldEvidence).where(FieldEvidence.extracted_field_id == f.id))
                params = {**f.value, **({"cap_age": cap} if cap and int(f.value.get("years", 0)) < 99 else {})}
                self.s.add(EligibilityRule(post_id=ref.post_id, rule_type="relaxation", params=params,
                                           clause_text=ev.quote if ev else None, evidence_id=ev.id if ev else None))
                n += 1
        self.s.flush()
        return n

    def _to_review(self, ef: ExtractedField, cycle: ExamCycle, reason: str, priority: int = 2) -> None:
        ef.status = "needs_review"
        if not self.s.scalar(select(ReviewTask.id).where(ReviewTask.extracted_field_id == ef.id, ReviewTask.status == "open")):
            self.review("field", reason, field=ef, cycle=cycle, priority=priority)

    def _apply_event(self, cycle: ExamCycle, cat: str | None, v: dict[str, Any], ef: ExtractedField, ev: FieldEvidence,
                     doc: Document, auto: bool, force: bool, actor: str, reason: str | None) -> None:
        etype = v["event_type"]
        try:
            d = date.fromisoformat(v["date"])
            d_end = date.fromisoformat(v["date_end"]) if v.get("date_end") else None
        except (KeyError, ValueError):
            ef.status, ef.validation_errors = "rejected", ["date did not parse"]
            return
        chk = check_event_date(etype, d, self.today, doc.published_on)
        label = f"{EVENT_TYPES.get(etype, etype)} ({v['stage']})" if v.get("stage") else None
        certainty = v.get("certainty", "official")
        precision = v.get("precision", "day")
        q = select(Event).where(Event.exam_cycle_id == cycle.id, Event.event_type == etype, Event.status == "active")
        q = q.where(Event.category_number == cat) if cat else q.where(Event.category_number.is_(None))
        q = q.where(Event.label == label) if label else q.where(Event.label.is_(None))
        existing = self.s.scalar(q)
        others: dict[str, list[date]] = {}
        for e in self.s.scalars(select(Event).where(Event.exam_cycle_id == cycle.id, Event.status == "active")):
            if e.date_start and e.precision == "day" and (not existing or e.id != existing.id) and (e.category_number == cat):
                others.setdefault(e.event_type, []).append(e.date_start)
        if precision == "day":
            others.setdefault(etype, []).append(d)
        errors = chk.errors + check_ordering(others)
        ef.validation_errors = errors or None
        if errors and not force:
            return self._to_review(ef, cycle, "; ".join(errors), priority=1)
        if existing:
            same = existing.date_start == d and existing.date_end == d_end and existing.precision == precision
            if same:
                if certainty == "official" and existing.certainty != "official":
                    existing.certainty = "official"
                existing.evidence_id = ev.id
                ef.status = "published"
                return
            if certainty == "tentative" and existing.certainty == "official" and not force:
                ef.status, ef.validation_errors = "rejected", ["tentative date does not override an official date"]
                return
            upgrade = existing.certainty != "official" and certainty == "official"
            if not (force or (auto and (upgrade or get_settings().auto_publish_revisions))):
                ef.status = "needs_review"
                self.review("revision",
                            f"{EVENT_TYPES.get(etype, etype)} for {cycle.title}: {existing.date_start} -> {d}"
                            + (" (category " + cat + ")" if cat else ""),
                            field=ef, cycle=cycle, priority=1,
                            payload={"event_id": existing.id, "new": {"date": d.isoformat(), "date_end": v.get("date_end"),
                                                                      "precision": precision, "certainty": certainty}})
                return
            self.publish_event(cycle, etype, label, cat, d, d_end, precision, certainty, ev, doc, existing,
                               reason or ("Official notice published" if upgrade else "Changed in the official source"), actor)
        else:
            if not auto:
                return self._to_review(ef, cycle, f"New {etype} date needs review (confidence {ef.confidence:.2f}, method {ef.method})")
            self.publish_event(cycle, etype, label, cat, d, d_end, precision, certainty, ev, doc, None, reason, actor)
        ef.status = "published"

    def publish_event(self, cycle: ExamCycle, etype: str, label: str | None, cat: str | None, d: date, d_end: date | None,
                      precision: str, certainty: str, ev: FieldEvidence | None, doc: Document | None,
                      existing: Event | None, reason: str | None, actor: str) -> Event:
        now = utcnow()
        new_val = {"date_start": d.isoformat(), "date_end": d_end.isoformat() if d_end else None, "precision": precision,
                   "certainty": certainty}
        if existing is None:
            e = Event(exam_cycle_id=cycle.id, event_type=etype, label=label, category_number=cat, date_start=d, date_end=d_end,
                      precision=precision, certainty=certainty, evidence_id=ev.id if ev else None)
            self.s.add(e)
            self.s.flush()
            rev = EventRevision(event_id=e.id, revision_no=1, kind="create", new_value=new_val, reason=reason,
                                source_url=doc.url if doc else cycle.official_url, document_id=doc.id if doc else None,
                                evidence_id=ev.id if ev else None, created_by=actor)
        else:
            e = existing
            old = {"date_start": e.date_start.isoformat() if e.date_start else None,
                   "date_end": e.date_end.isoformat() if e.date_end else None, "precision": e.precision, "certainty": e.certainty}
            e.date_start, e.date_end, e.precision, e.certainty = d, d_end, precision, certainty
            e.evidence_id = ev.id if ev else e.evidence_id
            e.revision_count += 1
            e.updated_at = now
            rev = EventRevision(event_id=e.id, revision_no=e.revision_count, kind="update", old_value=old, new_value=new_val,
                                reason=reason, source_url=doc.url if doc else None, document_id=doc.id if doc else None,
                                evidence_id=ev.id if ev else None, created_by=actor)
        self.s.add(rev)
        cycle.updated_at, cycle.is_fast_alert = now, False
        self.s.flush()
        if self.notify_enabled:
            notify.on_event_published(self.s, e, rev)
            if rev.kind == "create" and etype == "application_end":
                notify.on_new_matching_exam(self.s, cycle, self.today)
        return e

    # ------------------------------------------------------------------ news signals
    def run_news(self, src: Source) -> CrawlRun:
        run = CrawlRun(source_id=src.id)
        self.s.add(run)
        src.last_attempt_at = utcnow()
        src.runs_total += 1
        self.s.flush()
        try:
            res = self.client.get(src.url)
        except FetchError as e:
            return self._fail(src, run, "blocked" if isinstance(e, SourceBlocked) else "failed", str(e))
        feed_cfg = next((f for f in load_config().get("news_feeds", []) if f["key"] == src.key), {})
        entries = parse_feed(res.content, feed_cfg.get("publisher"))
        run.items_found = len(entries)
        orgs = {o.key: o for o in self.s.scalars(select(Organisation))}
        new = 0
        for e in entries:
            # Stories from earlier years are not news about current notices; they are skipped entirely.
            if e.published and (e.published.year < self.today.year or (self.today - e.published.date()).days > 90):
                continue
            if self.s.scalar(select(NewsItem.id).where(NewsItem.guid == e.guid[:600])):
                continue
            org = orgs.get(e.organisations[0])
            ni = NewsItem(source_id=src.id, guid=e.guid[:600], title=e.title[:600], url=e.url[:1500], publisher=e.publisher,
                          published_at=e.published, organisation_id=org.id if org else None,
                          public=get_settings().news_mentions_public)
            self.s.add(ni)
            self.s.flush()
            new += 1
            if org:
                match = self.match_official(org, e.title)
                if match:
                    ni.matched_exam_cycle_id = match.exam_cycle_id
                else:
                    self.s.add(MissedNoticeCandidate(news_item_id=ni.id, organisation_id=org.id, title=e.title[:600], url=e.url[:1500]))
                    for s2 in org.sources:
                        if s2.enabled and s2.kind != "manual":
                            s2.last_attempt_at = None  # re-check the official source on the next tick
        run.new_items = new
        run.status = "ok"
        return self._ok(src, run)

    def match_official(self, org: Organisation, title: str) -> SourceItem | None:
        since = utcnow() - timedelta(days=5)
        words = _stopless(title)
        best, score = None, 0.0
        src_ids = [s.id for s in org.sources]
        for si in self.s.scalars(select(SourceItem).where(SourceItem.source_id.in_(src_ids), SourceItem.first_seen_at >= since)):
            w = _stopless(si.title)
            if not w or not words:
                continue
            sc = len(words & w) / min(len(words), len(w))
            if sc > score:
                best, score = si, sc
        return best if score >= 0.4 else None

    # ------------------------------------------------------------------ scheduling and health
    def due_sources(self, now: datetime | None = None) -> list[Source]:
        now = now or utcnow()
        soon = self.today + timedelta(days=3)
        hot_orgs = set(self.s.scalars(
            select(Exam.organisation_id).join(ExamCycle).join(Event).where(
                Event.status == "active", Event.event_type.in_(["application_end", "confirmation_deadline"]),
                Event.date_start >= self.today, Event.date_start <= soon)))
        due = []
        for src in self.s.scalars(select(Source).where(Source.enabled.is_(True), Source.kind != "manual")):
            interval = src.every_minutes
            if src.organisation_id in hot_orgs and src.active_deadline_minutes:
                interval = src.active_deadline_minutes
            if src.status in ("blocked", "robots"):
                interval = max(interval, 24 * 60)
            if src.last_attempt_at is None or now - src.last_attempt_at >= timedelta(minutes=interval):
                due.append(src)
        return due

    def check_health(self, now: datetime | None = None) -> int:
        now = now or utcnow()
        flagged = 0
        for src in self.s.scalars(select(Source).where(Source.enabled.is_(True), Source.is_official.is_(True), Source.kind != "manual")):
            if src.last_success_at and now - src.last_success_at > timedelta(minutes=3 * src.every_minutes) and src.status == "ok":
                src.status = "stale"
                flagged += 1
            if src.last_new_item_at and now - src.last_new_item_at > timedelta(hours=src.expected_silence_hours):
                exists = self.s.scalar(select(ReviewTask.id).where(ReviewTask.source_id == src.id, ReviewTask.kind == "source_health",
                                                                 ReviewTask.status == "open"))
                if not exists:
                    self.review("source_health", f"{src.key}: no new items for {src.expected_silence_hours // 24} days.",
                                source=src, priority=3)
                    flagged += 1
        self.s.flush()
        return flagged
