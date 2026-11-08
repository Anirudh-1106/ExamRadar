"""Table-driven and property tests for the eligibility engine, including boundary dates."""

from datetime import date, timedelta

import pytest
from examradar_eligibility import Profile, Qualification, RuleSpec, countdown, evaluate
from hypothesis import given
from hypothesis import strategies as st

# The Kerala PSC Cat. 162/2026 rule, exactly as extracted from the real notification.
KPSC_AGE = RuleSpec("age", {"type": "born_between", "from": "1982-01-02", "to": "2008-01-01", "min_age": 18, "max_age": 44},
                    "Age Limit : 18 - 44. Only candidates born between 02/01/1982 and 01/01/2008 (both dates included)")
KPSC_REF = RuleSpec("relaxation_reference", {"categories": ["OBC", "SC", "ST"]})
BSC_RULE = RuleSpec("qualification", {"any_of": ["BSC_CHEMISTRY", "BSC_BIOCHEMISTRY", "BSC_BIOTECHNOLOGY", "BSC_MICROBIOLOGY"],
                                      "allow_equivalent": True})


def p(**kw):
    return Profile(**kw)


@pytest.mark.parametrize("dob,expected", [
    (date(1982, 1, 2), "eligible"),  # first day included
    (date(2008, 1, 1), "eligible"),  # last day included
    (date(1982, 1, 1), "not_eligible"),  # one day too old, general category
    (date(2008, 1, 2), "not_eligible"),  # one day too young
    (date(1995, 6, 15), "eligible"),
])
def test_age_boundaries(dob, expected):
    ev = evaluate([KPSC_AGE], p(date_of_birth=dob, category="GEN", kerala_community="OPEN", pwd=False, ex_serviceman=False))
    assert ev.status == expected


def test_missing_data_is_needs_check_not_a_guess():
    assert evaluate([KPSC_AGE], p()).status == "needs_check"
    assert evaluate([BSC_RULE], p(date_of_birth=date(1990, 1, 1))).status == "needs_check"
    assert evaluate([], p(date_of_birth=date(1990, 1, 1))).status == "needs_check"


def test_relaxation_reference_without_years_is_needs_check():
    ev = evaluate([KPSC_AGE, KPSC_REF], p(date_of_birth=date(1980, 5, 1), kerala_community="EZHAVA", pwd=False, ex_serviceman=False))
    assert ev.status == "needs_check" and "relaxation" in ev.results[0].explanation


def test_relaxation_with_years_and_cap():
    obc3 = RuleSpec("relaxation", {"applies_to": "OBC", "years": 3, "cap_age": 50})
    assert evaluate([KPSC_AGE, obc3], p(date_of_birth=date(1979, 1, 2), category="OBC")).status == "eligible"
    assert evaluate([KPSC_AGE, obc3], p(date_of_birth=date(1979, 1, 1), category="OBC")).status == "not_eligible"
    assert evaluate([KPSC_AGE, obc3], p(date_of_birth=date(1979, 1, 2), category="GEN", pwd=False, ex_serviceman=False)).status == "not_eligible"


@pytest.mark.parametrize("quals,expected", [
    ([Qualification("BSC_CHEMISTRY")], "eligible"),
    ([Qualification("BSC_CHEMISTRY", "final_year")], "needs_check"),
    ([Qualification("BSC_PHYSICS")], "needs_check"),  # same level; equivalence allowed, so check
    ([Qualification("SSLC"), Qualification("PLUS_TWO")], "not_eligible"),
    ([Qualification("MSC")], "needs_check"),  # master's does not imply a specific B.Sc subject
])
def test_qualification(quals, expected):
    assert evaluate([BSC_RULE], p(qualifications=quals)).status == expected


def test_appearing_allowed_and_percentage():
    rule = RuleSpec("qualification", {"any_of": ["DEGREE"], "allow_appearing": True, "min_percentage": 50})
    assert evaluate([rule], p(qualifications=[Qualification("BCOM", "appearing")])).status == "eligible"
    assert evaluate([rule], p(qualifications=[Qualification("BCOM", "completed", 48)])).status == "not_eligible"
    assert evaluate([rule], p(qualifications=[Qualification("BCOM", "completed")])).status == "needs_check"
    assert evaluate([rule], p(qualifications=[Qualification("BTECH_CS", "completed", 71)])).status == "eligible"


def test_free_text_qualification_is_always_needs_check():
    r = RuleSpec("qualification_text", {"text": "B.Sc Degree in Chemistry from a recognized University."})
    assert evaluate([r], p(qualifications=[Qualification("BSC_CHEMISTRY")])).status == "needs_check"


def test_community_attempts_language_domicile():
    st_only = RuleSpec("kerala_community", {"allowed": ["ST"]})
    assert evaluate([st_only], p(kerala_community="ST")).status == "eligible"
    assert evaluate([st_only], p(kerala_community="EZHAVA")).status == "not_eligible"
    att = RuleSpec("attempts", {"exam_slug": "upsc-civil-services", "max": 6, "by_category": {"OBC": 9, "SC": None, "ST": None}})
    assert evaluate([att], p(category="GEN", attempts={"upsc-civil-services": 6})).status == "not_eligible"
    assert evaluate([att], p(category="OBC", attempts={"upsc-civil-services": 6})).status == "eligible"
    assert evaluate([att], p(category="SC", attempts={"upsc-civil-services": 12})).status == "eligible"
    assert evaluate([att], p(category="GEN")).status == "needs_check"
    assert evaluate([RuleSpec("language", {"required": "malayalam"})], p(languages=["english"])).status == "not_eligible"
    assert evaluate([RuleSpec("domicile", {"states": ["KL"]})], p()).status == "needs_check"


def test_each_result_explains_itself():
    ev = evaluate([KPSC_AGE, BSC_RULE], p(date_of_birth=date(1995, 1, 1), qualifications=[Qualification("BSC_CHEMISTRY")]))
    for r in ev.results:
        assert r.requirement and r.explanation and r.outcome in ("pass", "fail", "unknown")
    assert ev.results[0].clause.startswith("Age Limit")


def test_countdown_is_a_labelled_projection():
    c = countdown([KPSC_AGE], p(date_of_birth=date(1990, 3, 10)), 2026)
    assert c[0]["last_year"] == 2026 + 8 and "Projection" in c[0]["basis"] and "may change" in c[0]["basis"]
    assert countdown([KPSC_AGE], p(date_of_birth=date(1970, 1, 1)), 2026)[0]["last_year"] is None


LO, HI = date(1982, 1, 2), date(2008, 1, 1)


@given(st.dates(min_value=date(1950, 1, 1), max_value=date(2015, 12, 31)))
def test_property_born_between_matches_definition(dob):
    ev = evaluate([KPSC_AGE], p(date_of_birth=dob, category="GEN", kerala_community="OPEN", pwd=False, ex_serviceman=False))
    assert (ev.status == "eligible") == (LO <= dob <= HI)


@given(st.dates(min_value=date(1950, 1, 1), max_value=date(2015, 12, 31)), st.integers(min_value=1, max_value=10))
def test_property_relaxation_never_hurts(dob, years):
    base = p(date_of_birth=dob, category="OBC")
    without = evaluate([KPSC_AGE], base).status
    with_r = evaluate([KPSC_AGE, RuleSpec("relaxation", {"applies_to": "OBC", "years": years})], base).status
    rank = {"not_eligible": 0, "needs_check": 1, "eligible": 2}
    assert rank[with_r] >= rank[without] or (without == "needs_check" and with_r == "not_eligible")


@given(st.dates(min_value=date(1960, 1, 1), max_value=date(2010, 12, 31)), st.integers(min_value=1, max_value=4000))
def test_property_older_is_never_more_eligible(dob, days):
    older = dob - timedelta(days=days)
    rank = {"not_eligible": 0, "needs_check": 1, "eligible": 2}
    young_status = evaluate([KPSC_AGE], p(date_of_birth=dob, category="GEN", pwd=False, ex_serviceman=False)).status
    old_status = evaluate([KPSC_AGE], p(date_of_birth=older, category="GEN", pwd=False, ex_serviceman=False)).status
    if dob <= HI:
        assert rank[old_status] <= rank[young_status]
