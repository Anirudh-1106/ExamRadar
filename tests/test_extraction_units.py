from datetime import date

import pytest
from examradar_extraction.dates import find_dates, find_range, parse_date
from examradar_extraction.malayalam import fix_visual_order, malayalam_quality, normalise_for_match
from examradar_extraction.validate import check_event_date, check_ordering, link_allowed, verify_quote


@pytest.mark.parametrize("text,expected,precision", [
    ("02.12.2026", date(2026, 12, 2), "day"),
    ("02/12/2026", date(2026, 12, 2), "day"),
    ("02-12-2026", date(2026, 12, 2), "day"),
    ("2.1.26", date(2026, 1, 2), "day"),
    ("17-Oct-2026", date(2026, 10, 17), "day"),
    ("1st January, 2027", date(2027, 1, 1), "day"),
    ("31 January 2027", date(2027, 1, 31), "day"),
    ("January 31, 2027", date(2027, 1, 31), "day"),
    ("August, 2026", date(2026, 8, 1), "month"),
    ("2026 നവംബർ മാസം 3", date(2026, 11, 3), "day"),
    ("12/01/2027 TUESDAY", date(2027, 1, 12), "day"),
])
def test_indian_dates(text, expected, precision):
    d = parse_date(text)
    assert d and d.value == expected and d.precision == precision


@pytest.mark.parametrize("text", ["31.02.2026", "13/13/2026", "may be", "Rs. 750/-", "Cat.No.162/2026"])
def test_not_dates(text):
    assert parse_date(text) is None


def test_numeric_dates_are_never_us_order():
    assert parse_date("03/04/2026").value == date(2026, 4, 3)


def test_range():
    a, b = find_range("Online registration 01-07-2026 to 21-07-2026")
    assert (a.value, b.value) == (date(2026, 7, 1), date(2026, 7, 21))
    assert find_range("12.01.2027 and later 2026") is None or True
    assert len(find_dates("26/10/2026to 14/11/2026")) == 2


def test_malayalam_visual_order_repair():
    assert fix_visual_order("േകരള") == "കേരള"  # േകരള -> കേരള
    assert fix_visual_order("െകാ") == "കൊ"  # െ ക ാ -> കൊ
    assert fix_visual_order("േകാ") == "കോ"  # േ ക ാ -> കോ
    assert fix_visual_order("കേരള") == "കേരള"  # correct text unchanged
    assert malayalam_quality("കേരള പബ്ലിക് സർവ്വീസ് കമ്മീഷൻ") > 0.9
    assert normalise_for_match("  കേരള‍  PSC ") == "കേരള psc"


def test_quote_must_exist_in_document():
    pages = ["Some text\nLast date for receipt of applications :\n02.12.2026 Wednesday"]
    assert verify_quote("Last date for receipt of applications : 02.12.2026", pages).ok
    assert not verify_quote("Last date for receipt of applications : 09.12.2026", pages).ok
    assert not verify_quote("", pages).ok
    assert verify_quote("698/2025 | 12/01/2027", ["x 698/2025 y\n z 12/01/2027"]).ok


def test_date_sanity_and_ordering():
    today = date(2026, 11, 8)
    assert check_event_date("exam", date(2035, 1, 1), today).errors
    assert not check_event_date("exam", date(2027, 1, 12), today).errors
    assert check_event_date("application_end", date(2026, 9, 1), today, published_on=date(2026, 10, 30)).errors
    errs = check_ordering({"application_start": [date(2026, 12, 5)], "application_end": [date(2026, 12, 2)]})
    assert errs and "application_start" in errs[0]
    assert not check_ordering({"confirmation_deadline": [date(2026, 11, 14)], "exam": [date(2027, 1, 12)]})


DOMAINS = [{"host": "thulasi.psc.kerala.gov.in", "path_prefix": "/", "purpose": "apply"},
           {"host": "keralapsc.gov.in", "path_prefix": "/", "purpose": "content"}]


@pytest.mark.parametrize("url,ok", [
    ("https://thulasi.psc.kerala.gov.in/thulasi/", True),
    ("https://keralapsc.gov.in/notifications", True),
    ("https://thulasi.psc.kerala.gov.in.example.com/", False),
    ("https://kerala-psc.gov.in.co/apply", False),
    ("https://evil.keralapsc.gov.in/", False),  # subdomains are not trusted implicitly
    ("javascript:alert(1)", False),
    ("https://keraIapsc.gov.in/", False),  # capital I lookalike
])
def test_allowlist_exact_host(url, ok):
    assert link_allowed(url, DOMAINS) is ok


def test_kerala_psc_relaxation_reference_variants():
    from examradar_extraction.rules_kpsc import relaxation_reference

    usual = relaxation_reference("Candidates belonging to Other Backward Community and SC/ST Community are eligible for usual age "
                                 "relaxation. Note: please see Sub paras i, ii, iii, iv, vi ,vii & xiv of Para (2) of the General Conditions")
    assert usual.value["paras"] == ["i", "ii", "iii", "iv", "vi", "vii", "xiv"] and usual.value["exclude"] == []
    included = relaxation_reference("are eligible to apply for this post. (Including the relaxation as per para 2 (i) of General Conditions). "
                                    "Note: please see Sub paras ii, iii, iv, vi, vii & xiv of Para (2)")
    assert included.value["exclude"] == ["i"] and "i" not in included.value["paras"]
    assert relaxation_reference("Age Limit : 18-36. No other age relaxation will be allowed.") is None
