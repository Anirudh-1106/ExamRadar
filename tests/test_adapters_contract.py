"""Adapter contract tests on saved official pages. A site layout change shows up here as a failed expectation."""

from datetime import date

import pytest
from examradar_adapters.base import Listing
from examradar_adapters.news import parse_feed
from examradar_adapters.registry import build_adapter, organisations
from examradar_extraction import rules_kpsc
from examradar_extraction.pdf import extract_pdf
from examradar_extraction.rules import generic_facts

from .conftest import fixture_bytes

ORGS = {o["key"]: o for o in organisations()}


def parse(key, url, rel):
    return build_adapter(ORGS[key]).parse_listing(Listing(url), fixture_bytes(rel), url)


def test_every_adapter_implements_the_contract():
    for key, cfg in ORGS.items():
        a = build_adapter(cfg)
        for m in ("discover", "fetch", "parse_listing", "classify", "extract"):
            assert callable(getattr(a, m)), (key, m)
        assert a.discover(), key


def test_kerala_psc_notifications_table():
    items = parse("kerala_psc", "https://keralapsc.gov.in/notifications", "kerala_psc/notifications.html")
    first = items[0]
    assert first.follow == ["https://keralapsc.gov.in/extra-ordinary-gazette-date-30102026"]
    assert first.data["category_numbers"][0] == "162/2026" and first.data["category_numbers"][-1] == "173/2026"
    end = [f for f in first.facts if f.value["event_type"] == "application_end"][0]
    assert end.value["date"] == "2026-12-02"


def test_kerala_psc_gazette_detail_and_notification_pdf():
    a = build_adapter(ORGS["kerala_psc"])
    items = a.parse_detail("https://keralapsc.gov.in/extra-ordinary-gazette-date-30102026",
                           fixture_bytes("kerala_psc/gazette_30102026.html"))
    assert len(items) >= 10
    multi = [i for i in items if len(i.cycle.category_numbers) > 1]
    assert multi and multi[0].cycle.category_numbers[:2] == ["165/2026", "166/2026"]
    facts = rules_kpsc.notification_facts(extract_pdf(fixture_bytes("kerala_psc/noti-162-26.pdf")))
    by = {f.field: f for f in facts}
    assert by["post"].value["name"] == "Laboratory Assistant (Dairy/CFP)"
    assert by["age_rule"].value == {"type": "born_between", "from": "1982-01-02", "to": "2008-01-01", "min_age": 18, "max_age": 44}
    assert "B.Sc Degree in Chemistry" in by["qualification"].value["text"]


def test_kerala_psc_programme_keeps_confirmation_programmes_separate():
    doc = extract_pdf(fixture_bytes("kerala_psc/for-confirmation-january-2027.pdf"), tables=True)
    facts = rules_kpsc.programme_facts(doc, "EXAMINATION PROGRAMME FOR THE MONTH OF JANUARY 2027 (FOR SUBMITTING CONFIRMATION)")
    assert all(f.value["programme"] == "for_confirmation" for f in facts)
    conf = [f for f in facts if f.value.get("event_type") == "confirmation_deadline"]
    assert conf and conf[0].value["date"] == "2026-11-14" and conf[0].value["window_start"] == "2026-10-26"
    assert any(f.field == "confirmation_note" for f in facts)


def test_kerala_psc_latest_ranked_lists():
    items = parse("kerala_psc", "https://keralapsc.gov.in/latest", "kerala_psc/latest.html")
    rl = [i for i in items if i.kind == "ranked_list"]
    assert rl and rl[0].facts[0].value["date"] == "2026-11-07" and rl[0].data["category_numbers"] == ["024/2025"]


def test_upsc_listings_and_notice():
    items = parse("upsc", "https://www.upsc.gov.in/examinations/active-exams", "upsc/active-exams.html")
    titles = [i.cycle.title for i in items if i.cycle]
    assert "Engineering Services Examination, 2027" in titles
    facts = generic_facts(extract_pdf(fixture_bytes("upsc/Notif-ESEP-2027-Engl-160926.pdf")))
    ev = {(f.value["event_type"], f.value.get("stage")): f.value["date"] for f in facts if f.field == "event"}
    assert ev[("application_end", None)] == "2026-10-06" and ev[("exam", "Preliminary")] == "2027-01-31"
    age = [f for f in facts if f.field == "age_rule"][0].value
    assert age["from"] == "1997-01-02" and age["to"] == "2006-01-01" and age["max_age"] == 30


def test_upsc_calendar_dates_are_tentative():
    from examradar_adapters.adapters.upsc import calendar_facts

    facts = calendar_facts(extract_pdf(fixture_bytes("upsc/calendar-2027.pdf")))
    assert len(facts) > 30 and all(f.value["certainty"] == "tentative" for f in facts)
    ese = [f for f in facts if f.value["cycle"]["title"] == "Engineering Services Examination, 2027"]
    by_stage = {(f.value["event_type"], f.value.get("stage")): f.value["date"] for f in ese}
    assert by_stage[("exam", "Preliminary")] == "2027-01-31" and by_stage[("exam", "Main")] == "2027-06-18"
    assert not [f for f in facts if "C.D.S." in f.value["cycle"]["title"]], "rows without their own dates produce nothing"


def test_sbi_openings_windows_and_apply_hosts():
    items = parse("sbi", "https://sbi.bank.in/web/careers/current-openings", "sbi/current-openings.html")
    main = [i for i in items if i.key == "sbi:CRPD/SCO/2026-27/29"][0]
    ev = {f.value["event_type"]: f.value["date"] for f in main.facts if f.field == "event"}
    assert ev == {"application_start": "2026-11-04", "application_end": "2026-11-25"}
    assert any(f.field == "link" and "ibpsreg.ibps.in" in f.value["url"] for f in main.facts)
    extended = [i for i in items if any(f.value.get("extended") for f in i.facts)]
    assert extended, "registration extensions are captured from the apply label"


def test_ibps_notification_tentative_schedule():
    facts = generic_facts(extract_pdf(fixture_bytes("ibps/Detailed-Notification_CRP-PO-XVI.pdf")))
    ev = [f for f in facts if f.field == "event" and f.value["event_type"] == "exam"]
    assert ev and all(f.value["certainty"] == "tentative" for f in ev)
    assert {(f.value["stage"], f.value["date"]) for f in ev} == {("Preliminary", "2026-08-01"), ("Main", "2026-10-01")}
    specs = {f.value["item"]: f.value for f in facts if f.field == "photo_spec"}
    assert specs["signature"]["width"] == 140 and specs["signature"]["max_kb"] == 20


def test_nta_rrb_kdrb_rbi_listings():
    nta = parse("nta", "https://nta.ac.in/", "nta/home.html")
    assert nta and all(i.doc_urls and i.published_hint for i in nta[:5])
    rrb = parse("rrb", "https://rrb.indianrailways.gov.in/thiruvananthapuram", "rrb/thiruvananthapuram.html")
    assert any(i.data["cen"] == "09/2026" for i in rrb) and all(i.data["fetch"] is False for i in rrb)
    kdrb = parse("kdrb", "https://kdrb.kerala.gov.in/category/examination/notifications/", "kdrb/notifications.html")
    assert kdrb and kdrb[0].facts[0].value["date"] == "2026-06-10"
    assert parse("rbi", "https://www.rbi.org.in/pressreleases_rss.xml", "rbi/pressreleases_rss.xml") == []


def test_news_feeds_are_matched_to_organisations():
    entries = parse_feed(fixture_bytes("news/indianexpress_jobs.rss"))
    assert entries and all(e.organisations for e in entries)


@pytest.mark.parametrize("rel", ["kerala_psc/noti-162-26.pdf", "upsc/Notif-ESEP-2027-Engl-160926.pdf", "sbi/JA_2026_Detailed_Advt_Eng.pdf"])
def test_pdfs_have_usable_text(rel):
    d = extract_pdf(fixture_bytes(rel))
    assert d.quality > 0.8 and len(d.text) > 5000


def test_today_is_not_hardcoded():
    assert date.today().year >= 2026


def test_ssc_rendered_notice_board():
    items = parse("ssc", "https://ssc.gov.in/", "ssc/home_rendered.html")
    dated = [i for i in items if i.published_hint]
    assert len(dated) >= 8 and all(i.data.get("fetch") is False for i in dated)
    assert any(i.kind == "answer_key" for i in dated)
    assert any(i.cycle and i.cycle.title == "Combined Graduate Level Examination, 2026" for i in dated)


@pytest.mark.parametrize("key,rel,url,minimum", [
    ("cmd_kerala", "cmd_kerala/recruitment.html", "https://cmd.kerala.gov.in/recruitment/", 8),
    ("ctet", "ctet/home.html", "https://ctet.nic.in/", 5),
    ("isro", "isro/current-opportunities.html", "https://www.isro.gov.in/CurrentOpportunities.html", 20),
    ("nvs", "nvs/home_rendered.html", "https://navodaya.gov.in/nvs/en/Home1", 10),
    ("kerala_hc", "kerala_hc/notifications_rendered.html", "https://hckrecruitment.keralacourts.in/hckrecruitment/Recruitment/notifications", 10),
    ("lic", "lic/careers_rendered.html", "https://licindia.in/careers", 1),
    ("drdo", "drdo/vacancies.html", "https://xn--m1b0a2bb8esed.xn--11b7cb3a6a.xn--h2brj9c/drdo/en/offerings/vacancies", 1),
])
def test_later_sources_via_configurable_adapter(key, rel, url, minimum):
    items = parse(key, url, rel)
    assert len(items) >= minimum, (key, len(items))
    for i in items:
        assert i.url is None or build_adapter(ORGS[key])._ok_url(i.url) or i.url == url
        assert len(i.title) >= 12


def test_isro_grid_gives_official_windows_and_ktet_uses_file_names():
    items = parse("isro", "https://www.isro.gov.in/CurrentOpportunities.html", "isro/current-opportunities.html")
    first = [i for i in items if i.key == "ISRO:ICRB:01(A-JPA):2026"][0]
    assert {f.value["event_type"]: f.value["date"] for f in first.facts} == {"application_start": "2026-07-27", "application_end": "2026-08-20"}
    # Every entry keeps its own number; undated entries never borrow a neighbour's dates.
    assert all(i.cycle and i.cycle.notification_number for i in items)
    assert not any(f.value["date"] for i in items if i.key == "SAC:01:2026" for f in i.facts)
    # VSSC-301 is undated but numbered below VSSC-322, which closed in January 2023.
    assert not any(i.key == "VSSC-301" for i in items)
    ktet = parse("ktet", "https://ktet.kerala.gov.in/", "ktet/home.html")
    assert any(i.cycle and i.cycle.title == "K-TET Sep 2026" and i.kind == "notification" for i in ktet)
    nvs = parse("nvs", "https://navodaya.gov.in/nvs/en/Home1", "nvs/home_rendered.html")
    assert any(i.kind == "admit_card" for i in nvs) and all(i.published_hint for i in nvs)
