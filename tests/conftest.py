"""Test setup: temporary database and storage, and an HTTP transport that serves saved official documents.

Fixture documents are real pages and PDFs fetched from official sites on 2026-11-08 (see data/fixtures/manifest.yaml).
"""

import os
from pathlib import Path

import httpx
import pytest

os.environ.setdefault("APP_ENV", "test")

from examradar_adapters.http import PoliteClient  # noqa: E402
from examradar_core import db as dbmod  # noqa: E402
from examradar_core.models import Base  # noqa: E402
from examradar_core.storage import LocalStore, set_store  # noqa: E402

FIX = Path(__file__).resolve().parents[1] / "data" / "fixtures"

URLS = {
    "https://keralapsc.gov.in/notifications": "kerala_psc/notifications.html",
    "https://keralapsc.gov.in/examinations": "kerala_psc/examinations.html",
    "https://keralapsc.gov.in/latest": "kerala_psc/latest.html",
    "https://keralapsc.gov.in/extra-ordinary-gazette-date-30102026": "kerala_psc/gazette_30102026.html",
    "https://keralapsc.gov.in/sites/default/files/2026-10/noti-162-26.pdf": "kerala_psc/noti-162-26.pdf",
    "https://keralapsc.gov.in/sites/default/files/2026-10/for-confirmation-january-2027.pdf": "kerala_psc/for-confirmation-january-2027.pdf",
    "https://keralapsc.gov.in/general-conditions": "kerala_psc/general-conditions.html",
    "https://keralapsc.gov.in/sites/default/files/inline-files/general_conditions_added_latest.pdf": "kerala_psc/general_conditions_added_latest.pdf",
    "https://www.upsc.gov.in/whats-new": "upsc/whats-new.html",
    "https://www.upsc.gov.in/examinations/active-exams": "upsc/active-exams.html",
    "https://www.upsc.gov.in/examinations/exam-calendar": "upsc/exam-calendar.html",
    "https://www.upsc.gov.in/examinations/Engineering%20Services%20%28Preliminary%29%20Examination%2C%202027": "upsc/exam-ese-2027.html",
    "https://www.upsc.gov.in/sites/default/files/Notif-ESEP-2027-Engl-160926.pdf": "upsc/Notif-ESEP-2027-Engl-160926.pdf",
    "https://sbi.bank.in/web/careers/current-openings": "sbi/current-openings.html",
    "https://www.ibps.in/": "ibps/home.html",
    "https://nta.ac.in/": "nta/home.html",
    "https://rrb.indianrailways.gov.in/thiruvananthapuram": "rrb/thiruvananthapuram.html",
    "https://kdrb.kerala.gov.in/category/examination/notifications/": "kdrb/notifications.html",
    "https://www.rbi.org.in/pressreleases_rss.xml": "rbi/pressreleases_rss.xml",
    "https://indianexpress.com/section/jobs/feed/": "news/indianexpress_jobs.rss",
    "https://www.thehindu.com/education/feeder/default.rss": "news/thehindu_education.rss",
    "https://www.mathrubhumi.com/rss": "news/mathrubhumi.rss",
}


def ctype(path: str) -> str:
    if path.endswith(".pdf"):
        return "application/pdf"
    if path.endswith((".rss", ".xml")):
        return "application/rss+xml"
    return "text/html; charset=utf-8"


class FixtureTransport(httpx.BaseTransport):
    def __init__(self, overrides: dict[str, bytes | tuple[int, bytes]] | None = None):
        self.overrides = overrides or {}
        self.requests: list[str] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url)
        if url in self.overrides:
            v = self.overrides[url]
            status, body = v if isinstance(v, tuple) else (200, v)
            return httpx.Response(status, content=body, headers={"content-type": ctype(url)})
        if url.endswith("/robots.txt"):
            return httpx.Response(404, content=b"not found")
        rel = URLS.get(url)
        if rel is None:
            return httpx.Response(404, content=b"not found")
        return httpx.Response(200, content=(FIX / rel).read_bytes(), headers={"content-type": ctype(rel)})


@pytest.fixture
def transport():
    return FixtureTransport()


@pytest.fixture
def client(transport):
    return PoliteClient(min_delay=0, transport=transport)


@pytest.fixture
def db(tmp_path):
    engine = dbmod.make_engine(f"sqlite:///{(tmp_path / 't.db').as_posix()}")
    Base.metadata.create_all(engine)
    dbmod.set_engine(engine)
    set_store(LocalStore(str(tmp_path / "objects")))
    s = dbmod.session_factory()()
    from examradar_worker.registry_sync import sync_registry

    sync_registry(s)
    s.commit()
    yield s
    s.close()
    engine.dispose()


def fixture_bytes(rel: str) -> bytes:
    return (FIX / rel).read_bytes()
