from datetime import date

import pyotp
import pytest
from examradar_api import scam as scam_mod
from examradar_api.main import app
from examradar_api.middleware import buckets
from examradar_core.models import AdminUser, ReviewTask, Source
from examradar_worker.pipeline import Pipeline
from fastapi.testclient import TestClient
from sqlalchemy import select

TODAY = date(2026, 11, 8)


@pytest.fixture
def api(db, client, monkeypatch):
    p = Pipeline(db, client=client, today=TODAY)
    for key in ("kerala_psc:https://keralapsc.gov.in/notifications", "kerala_psc:https://keralapsc.gov.in/examinations",
                "upsc:https://www.upsc.gov.in/examinations/active-exams"):
        p.run_source(db.scalar(select(Source).where(Source.key == key)))
    p.process_documents(40)
    db.commit()
    monkeypatch.setattr(scam_mod, "rdap_age_days", lambda domain, client=None: 20 if "fake" in domain else 4000)

    def no_fetch(*a, **k):
        raise scam_mod.UnsafeURL("network disabled in tests")

    monkeypatch.setattr(scam_mod, "safe_get", no_fetch)
    monkeypatch.setattr("examradar_api.deps.ist_today", lambda: TODAY)
    buckets.state.clear()
    return TestClient(app)


def test_exam_search_detail_and_calendar(api):
    r = api.get("/v1/exams", params={"q": "162/2026"})
    assert r.status_code == 200 and r.json()["total"] == 1
    ex = r.json()["items"][0]
    assert ex["organisation"]["key"] == "kerala_psc" and ex["status"] == "open"
    assert ex["application_end"]["date_start"] == "2026-12-02" and ex["application_end"]["certainty"] == "official"
    d = api.get(f"/v1/exams/{ex['id']}").json()
    end = [e for e in d["events"] if e["event_type"] == "application_end"][0]
    assert end["evidence"]["quote"] and end["evidence"]["source_url"].startswith("https://keralapsc.gov.in")
    assert d["apply"]["host"] == "thulasi.psc.kerala.gov.in" and d["apply"]["copy_text"] == "162/2026"
    assert "not affiliated" in d["disclaimer"]
    assert d["posts"][0]["rules"]
    cal = api.get("/v1/calendar", params={"start": "2026-11-01", "end": "2027-02-28"}).json()
    assert any(c["event_type"] == "confirmation_deadline" for c in cal)
    assert api.get("/v1/calendar", params={"start": "2026-01-01", "end": "2028-12-31"}).status_code == 422
    kerala = api.get("/v1/exams", params={"group": "kerala", "page_size": 5}).json()
    assert kerala["page_size"] == 5 and all(i["organisation"]["group"] == "kerala" for i in kerala["items"])


def test_sources_meta_and_notices(api):
    src = api.get("/v1/sources").json()
    rbi = [x for x in src if x["key"] == "rbi:manual"][0]
    assert rbi["status"] == "manual" and "manual" in rbi["note"].lower() or "team" in rbi["note"]
    meta = api.get("/v1/meta").json()
    assert meta["app_name"] and any(q["code"] == "BSC_CHEMISTRY" for q in meta["qualifications"])
    assert api.get("/v1/notices").json()["items"]
    assert r_ok(api.get("/healthz")) and r_ok(api.get("/readyz"))


def r_ok(r):
    return r.status_code == 200


def test_device_profile_saved_status_export_delete(api):
    reg = api.post("/v1/devices/register", json={"platform": "android", "app_version": "0.1.0"}).json()
    h = {"Authorization": f"Bearer {reg['token']}"}
    assert api.get("/v1/me/exams").status_code == 401
    ex_id = api.get("/v1/exams", params={"q": "162/2026"}).json()["items"][0]["id"]
    assert api.put(f"/v1/me/exams/{ex_id}", headers=h).status_code == 204
    assert api.put(f"/v1/me/exams/{ex_id}/status", headers=h, json={"status": "applied"}).status_code == 204
    mine = api.get("/v1/me/exams", headers=h).json()
    assert mine[0]["status"] == "applied"
    prof = {"date_of_birth": "1995-04-01", "category": "OBC", "kerala_community": "EZHAVA",
            "qualifications": [{"code": "BSC_CHEMISTRY", "status": "completed"}]}
    assert api.put("/v1/me/profile", headers=h, json={"consent": False, "data": prof}).status_code == 422
    assert api.put("/v1/me/profile", headers=h, json={"consent": True, "data": prof}).status_code == 200
    el = api.get("/v1/me/eligibility", headers=h).json()
    post = el[0]["posts"][0]
    assert post["status"] in ("eligible", "needs_check") and post["results"]
    age = [x for x in post["results"] if x["rule_type"] == "age"][0]
    assert age["outcome"] == "pass" and age["clause"]
    exp = api.get("/v1/me/export", headers=h).json()
    assert exp["profile"]["date_of_birth"] == "1995-04-01" and exp["saved_exams"]
    prefs = api.get("/v1/me/preferences", headers=h).json()
    prefs["interests"] = {"organisations": ["kerala_psc"]}
    assert api.put("/v1/me/preferences", headers=h, json=prefs).json()["interests"] == {"organisations": ["kerala_psc"]}
    assert api.delete("/v1/me", headers=h).status_code == 204
    assert api.get("/v1/me/exams", headers=h).status_code == 401


def test_stateless_eligibility_stores_nothing(api, db):
    from examradar_core.models import UserProfile

    ex_id = api.get("/v1/exams", params={"q": "162/2026"}).json()["items"][0]["id"]
    r = api.post("/v1/eligibility/evaluate", json={"profile": {"date_of_birth": "2009-01-01"}, "exam_ids": [ex_id]}).json()
    assert r[0]["status"] == "not_eligible"
    assert not db.scalars(select(UserProfile)).all()


@pytest.mark.parametrize("kind,value,verdict", [
    ("url", "https://keralapsc.gov.in/notifications", "Verified on official source"),
    ("url", "https://keralapsc.gov.in.apply-now.fake.in/form", "Suspicious"),
    ("url", "http://keralapssc.gov.in/", "Suspicious"),
    ("url", "https://bit.ly/abc123", "Suspicious"),
    ("url", "https://sites.google.com/view/psc-recruitment", "Suspicious"),
    ("text", "Kerala PSC Cat.No. 162/2026 Laboratory Assistant. Last date 02.12.2026.", "Verified on official source"),
    ("text", "Railway job guaranteed! Pay Rs 1500 registration fee to rrbjobs@ybl via Google Pay. No exam required.", "Suspicious"),
    ("text", "Some recruitment notice with no numbers at all here.", "Not found on official sources"),
])
def test_scam_check_verdicts(api, kind, value, verdict):
    r = api.post("/v1/scam-check", json={"kind": kind, "value": value})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] == verdict, body
    assert body["evidence"] and "cannot prove" in body["disclaimer"]


def test_scam_known_fake_and_pdf(api, db):
    from examradar_core.models import FactCheckItem

    db.add(FactCheckItem(source_url="https://pib.gov.in/x", title="Fake railway recruitment", keywords=["railway", "group d", "whatsapp"], added_by="t"))
    db.commit()
    r = api.post("/v1/scam-check", json={"kind": "text", "value": "Railway Group D vacancy, apply on WhatsApp 9876543210"}).json()
    assert r["verdict"] == "Known fake"
    pdf = open("data/fixtures/kerala_psc/noti-162-26.pdf", "rb").read()
    r = api.post("/v1/scam-check/pdf", files={"file": ("n.pdf", pdf, "application/pdf")}).json()
    assert r["verdict"] in ("Verified on official source", "Not found on official sources", "Suspicious")
    assert api.post("/v1/scam-check/pdf", files={"file": ("n.pdf", b"hello", "application/pdf")}).status_code == 422


def test_scam_text_is_purged(api, db):
    from datetime import timedelta

    from examradar_core.models import ScamCheck
    from examradar_worker import jobs

    api.post("/v1/scam-check", json={"kind": "text", "value": "Some recruitment notice with no numbers at all here."})
    row = db.scalars(select(ScamCheck)).first()
    row.purge_after = row.purge_after - timedelta(days=2)
    db.commit()
    assert jobs.purge_scam_text() == 1
    db.expire_all()
    assert db.scalars(select(ScamCheck)).first().submitted_text is None


def test_ssrf_protection():
    from examradar_api.safe_fetch import UnsafeURL, validate_url

    for bad in ("http://127.0.0.1/", "http://localhost/admin", "http://169.254.169.254/latest", "http://10.0.0.5/",
                "file:///etc/passwd", "http://user:pw@example.com/", "http://example.com:8080/", "http://[::1]/"):
        with pytest.raises(UnsafeURL):
            validate_url(bad)


def test_admin_requires_login_totp_and_csrf(api, db):
    from examradar_api.admin_auth import create_admin

    secret = create_admin(db, "admin@example.com", "correct horse battery")
    db.commit()
    assert api.get("/admin", follow_redirects=False).status_code == 303
    bad = api.post("/admin/login", data={"email": "admin@example.com", "password": "correct horse battery", "code": "000000"})
    assert "Invalid credentials" in bad.text
    ok = api.post("/admin/login", data={"email": "admin@example.com", "password": "correct horse battery",
                                        "code": pyotp.TOTP(secret).now()}, follow_redirects=False)
    assert ok.status_code == 303
    assert "open reviews" in api.get("/admin").text
    task = db.scalar(select(ReviewTask).where(ReviewTask.status == "open", ReviewTask.extracted_field_id.is_not(None)))
    assert task is not None
    page = api.get(f"/admin/review/{task.id}")
    assert page.status_code == 200 and "Supporting text" in page.text
    assert api.post(f"/admin/review/{task.id}/reject", data={"reason": "x"}).status_code == 403
    csrf = page.text.split('name="csrf" value="')[1].split('"')[0]
    assert api.post(f"/admin/review/{task.id}/reject", data={"reason": "wrong", "csrf": csrf}, follow_redirects=False).status_code == 303
    db.expire_all()
    assert db.get(ReviewTask, task.id).status == "rejected"
    for path in ("/admin/sources", "/admin/manual", "/admin/missed", "/admin/factcheck", "/admin/notifications", "/admin/audit", "/admin/exams"):
        assert api.get(path).status_code == 200, path
    assert db.scalar(select(AdminUser)).last_login_at is not None


def test_openapi_has_v1_paths(api):
    spec = api.get("/openapi.json").json()
    for path in ("/v1/exams", "/v1/exams/{exam_id}", "/v1/calendar", "/v1/scam-check", "/v1/me/export", "/v1/sources"):
        assert path in spec["paths"]
    assert not any(p.startswith("/admin") for p in spec["paths"])
