"""Eligibility evaluation.

Each rule returns pass, fail, or unknown with the user's value, the requirement, and the supporting clause.
Overall: any fail -> not_eligible; otherwise any unknown -> needs_check; otherwise eligible. No rules -> needs_check.
"""

from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

KERALA_OBC_GROUPS = {"EZHAVA", "MUSLIM", "LC_AI", "OBC_OTHER", "VISWAKARMA", "SIUC_NADAR", "HINDU_NADAR", "DHEEVARA"}


@lru_cache
def taxonomy() -> dict[str, Any]:
    data = yaml.safe_load((Path(__file__).parent / "data" / "qualifications.yaml").read_text(encoding="utf-8"))
    return data


@lru_cache
def _quals() -> dict[str, dict[str, Any]]:
    return {q["code"]: q for q in taxonomy()["qualifications"]}


def implied(code: str) -> set[str]:
    """A qualification plus everything it presupposes."""
    out, q = set(), _quals().get(code)
    while q:
        out.add(q["code"])
        q = _quals().get(q.get("parent", ""))
    return out


@dataclass
class Qualification:
    code: str
    status: str = "completed"  # completed | final_year | appearing
    percentage: float | None = None


@dataclass
class Profile:
    date_of_birth: date | None = None
    category: str | None = None  # GEN | EWS | OBC | SC | ST
    kerala_community: str | None = None
    pwd: bool | None = None
    ex_serviceman: bool | None = None
    gender: str | None = None
    nationality: str | None = None
    domicile_state: str | None = None
    qualifications: list[Qualification] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    attempts: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Profile":
        raw = d.get("date_of_birth")
        dob: date | None = date.fromisoformat(raw) if isinstance(raw, str) and raw else (raw if isinstance(raw, date) else None)
        return cls(
            date_of_birth=dob,
            category=d.get("category"), kerala_community=d.get("kerala_community"), pwd=d.get("pwd"),
            ex_serviceman=d.get("ex_serviceman"), gender=d.get("gender"), nationality=d.get("nationality"),
            domicile_state=d.get("domicile_state"),
            qualifications=[Qualification(**q) if isinstance(q, dict) else Qualification(q) for q in d.get("qualifications") or []],
            languages=[x.lower() for x in d.get("languages") or []], attempts=d.get("attempts") or {},
        )

    def relaxation_groups(self) -> set[str]:
        g = set()
        if self.category:
            g.add(self.category.upper())
        kc = (self.kerala_community or "").upper()
        if kc in KERALA_OBC_GROUPS:
            g.add("OBC")
        if kc in ("SC", "SCCC"):
            g.add("SC")
        if kc == "ST":
            g.add("ST")
        if self.pwd:
            g.add("PWBD")
        if self.ex_serviceman:
            g.add("EXSM")
        if (self.gender or "").lower() == "female":
            g.add("FEMALE")
        return g


@dataclass
class RuleSpec:
    rule_type: str
    params: dict[str, Any]
    clause: str | None = None
    source_url: str | None = None
    page: int | None = None


@dataclass
class RuleResult:
    rule_type: str
    outcome: str  # pass | fail | unknown
    user_value: str | None
    requirement: str
    explanation: str
    clause: str | None = None
    source_url: str | None = None
    page: int | None = None


@dataclass
class Evaluation:
    status: str  # eligible | not_eligible | needs_check
    results: list[RuleResult]


def age_on(dob: date, on: date) -> int:
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


def _shift_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 Feb
        return d.replace(year=d.year + years, day=28)


def _fmt(d: date) -> str:
    return d.strftime("%d %b %Y")


def _age_rule(spec: RuleSpec, p: Profile, relax: list[RuleSpec]) -> RuleResult:
    v = spec.params
    base: dict[str, Any] = dict(rule_type="age", clause=spec.clause, source_url=spec.source_url, page=spec.page)
    if v.get("type") == "born_between":
        lo, hi = date.fromisoformat(v["from"]), date.fromisoformat(v["to"])
        req = f"Born between {_fmt(lo)} and {_fmt(hi)}"
    elif v.get("cutoff_date") and v.get("max_age") is not None:
        # Without explicit birth dates the boundary year is ambiguous ("18-44" and "must not have attained 30"
        # are worded differently by different bodies), so the boundary year itself is needs_check.
        cut = date.fromisoformat(v["cutoff_date"])
        mn, mx = int(v.get("min_age", 0)), int(v["max_age"])
        req = f"Age {mn} to {mx} on {_fmt(cut)}"
        if p.date_of_birth is None:
            return RuleResult(**base, outcome="unknown", user_value=None, requirement=req, explanation="Add your date of birth to check this.")
        a = age_on(p.date_of_birth, cut)
        uv = f"Age {a} on {_fmt(cut)}"
        if mn < a < mx:
            return RuleResult(**base, outcome="pass", user_value=uv, requirement=req, explanation="Your age is within the limit.")
        if a < mn - 0 or a > mx:
            return RuleResult(**base, outcome="fail" if not relax else "unknown", user_value=uv, requirement=req,
                              explanation="Your age is outside the limit." + (" A relaxation may apply." if relax else ""))
        return RuleResult(**base, outcome="unknown", user_value=uv, requirement=req,
                          explanation="You are at the edge of the age limit. Check the exact wording in the notification.")
    else:
        return RuleResult(**base, outcome="unknown", user_value=None, requirement="Age limit",
                          explanation="The age rule is not in a form we can check. Read the clause.")
    if p.date_of_birth is None:
        return RuleResult(**base, outcome="unknown", user_value=None, requirement=req,
                          explanation="Add your date of birth to check this.")
    dob = p.date_of_birth
    uv = f"Born {_fmt(dob)}"
    if dob > hi:
        return RuleResult(**base, outcome="fail", user_value=uv, requirement=req, explanation="You are younger than the minimum age.")
    if dob >= lo:
        return RuleResult(**base, outcome="pass", user_value=uv, requirement=req, explanation="Your date of birth is within the limit.")
    groups = p.relaxation_groups()
    rel = [r for r in relax if r.rule_type == "relaxation" and str(r.params.get("applies_to", "")).upper() in groups]
    firm = max((int(r.params.get("years", 0)) for r in rel if not r.params.get("conditional")), default=0)
    cond = [r for r in rel if r.params.get("conditional")]
    cap = next((r.params.get("cap_age") for r in relax if r.params.get("cap_age")), None)

    def earliest(years: int, capped: bool = True) -> date:
        lo2 = _shift_years(lo, -years)
        if capped and cap and v.get("max_age") is not None and v.get("type") == "born_between":
            lo2 = max(lo2, _shift_years(lo, -(int(cap) - int(v["max_age"]))))
        return lo2

    if firm and dob >= earliest(firm):
        return RuleResult(**base, outcome="pass", user_value=uv, requirement=f"{req}, relaxed by {firm} years",
                          explanation=f"Eligible with the {firm}-year age relaxation that applies to you.")
    for r in sorted(cond, key=lambda r: -int(r.params.get("years", 0))):
        yrs = int(r.params.get("years", 0))
        if dob >= earliest(max(firm, yrs), capped=yrs < 99):
            return RuleResult(**base, outcome="unknown", user_value=uv, requirement=req,
                              explanation="You may be eligible through an age relaxation that depends on your circumstances. "
                                          + str(r.params.get("note", "")) + " Check before applying.")
    # Relaxations exist for groups the profile has not answered yet (disability, ex-serviceman).
    unanswered = {"PWBD": p.pwd is None, "EXSM": p.ex_serviceman is None}
    if any(unanswered.get(str(r.params.get("applies_to", "")).upper()) for r in relax if r.rule_type == "relaxation"):
        return RuleResult(**base, outcome="unknown", user_value=uv, requirement=req,
                          explanation="You are above the base limit. Tell us whether you are a person with disability or an "
                                      "ex-serviceman to check the age relaxation.")
    if firm:
        return RuleResult(**base, outcome="fail", user_value=uv, requirement=f"{req}, relaxed by {firm} years",
                          explanation="You are above the upper age limit even with relaxation.")
    if any(r.rule_type == "relaxation" for r in relax) and (p.category or p.kerala_community):
        return RuleResult(**base, outcome="fail", user_value=uv, requirement=req,
                          explanation="You are above the upper age limit, and no age relaxation applies to your category.")
    ref = [r for r in relax if r.rule_type == "relaxation_reference"]
    if any(groups & {c.upper() for c in r.params.get("categories", [])} for r in ref) or (
            ref and (p.pwd is None or p.ex_serviceman is None)):
        return RuleResult(**base, outcome="unknown", user_value=uv, requirement=req,
                          explanation="You are above the base limit. An age relaxation may apply to you; the notification "
                                      "refers to its general conditions for the amount. Check before applying.")
    if p.category is None and p.kerala_community is None:
        return RuleResult(**base, outcome="unknown", user_value=uv, requirement=req,
                          explanation="You are above the base limit. Add your category to check age relaxation.")
    return RuleResult(**base, outcome="fail", user_value=uv, requirement=req, explanation="You are above the upper age limit.")


def _qual_rule(spec: RuleSpec, p: Profile) -> RuleResult:
    v = spec.params
    base: dict[str, Any] = dict(rule_type="qualification", clause=spec.clause, source_url=spec.source_url, page=spec.page)
    if spec.rule_type == "qualification_text":
        return RuleResult(**base, outcome="unknown", user_value=", ".join(q.code for q in p.qualifications) or None,
                          requirement=(v.get("text") or "See notification")[:300],
                          explanation="This qualification is written in the notification's own words. Compare it yourself; "
                                      "equivalent qualifications may also be accepted.")
    need = set(v.get("any_of", []))
    names = ", ".join(_quals().get(c, {"name": c})["name"] for c in sorted(need))
    req = f"One of: {names}" + (" (or equivalent)" if v.get("allow_equivalent") else "")
    if not p.qualifications:
        return RuleResult(**base, outcome="unknown", user_value=None, requirement=req, explanation="Add your qualifications to check this.")
    have_done = set().union(*[implied(q.code) for q in p.qualifications if q.status == "completed"]) if p.qualifications else set()
    have_pending = set().union(*[implied(q.code) for q in p.qualifications if q.status != "completed"]) if p.qualifications else set()
    uv = ", ".join(f"{_quals().get(q.code, {'name': q.code})['name']} ({q.status.replace('_', ' ')})" for q in p.qualifications)
    min_pct = v.get("min_percentage")
    if need & have_done:
        if min_pct is not None:
            pcts = [q.percentage for q in p.qualifications if implied(q.code) & need and q.status == "completed"]
            if not pcts or any(x is None for x in pcts):
                return RuleResult(**base, outcome="unknown", user_value=uv, requirement=f"{req}, minimum {min_pct}%",
                                  explanation="Add your percentage to check the minimum marks.")
            if max(x for x in pcts if x is not None) < float(min_pct):
                return RuleResult(**base, outcome="fail", user_value=uv, requirement=f"{req}, minimum {min_pct}%",
                                  explanation="Your marks are below the minimum.")
        return RuleResult(**base, outcome="pass", user_value=uv, requirement=req, explanation="You have the required qualification.")
    if need & have_pending:
        if v.get("allow_appearing"):
            return RuleResult(**base, outcome="pass", user_value=uv, requirement=req,
                              explanation="Final-year or appearing candidates may apply. You must complete it by the date the notice sets.")
        return RuleResult(**base, outcome="unknown", user_value=uv, requirement=req,
                          explanation="You have not completed this qualification yet. Check whether appearing candidates are allowed.")
    if v.get("allow_equivalent"):
        levels = [_quals()[c]["level"] for c in need if c in _quals()]
        floor = min(levels) if levels else 99
        if any(_quals().get(q.code, {}).get("level", 0) >= floor for q in p.qualifications):
            return RuleResult(**base, outcome="unknown", user_value=uv, requirement=req,
                              explanation="Your qualification may be accepted as equivalent or higher. Check the equivalence list.")
    return RuleResult(**base, outcome="fail", user_value=uv, requirement=req, explanation="Your qualifications do not include this.")


def _simple(spec: RuleSpec, p: Profile) -> RuleResult:
    v, t = spec.params, spec.rule_type
    base: dict[str, Any] = dict(rule_type=t, clause=spec.clause, source_url=spec.source_url, page=spec.page)
    lookup = {"nationality": (p.nationality, "allowed"), "gender": (p.gender, "allowed"),
              "category": (p.category, "allowed"), "kerala_community": (p.kerala_community, "allowed"),
              "domicile": (p.domicile_state, "states")}
    if t in lookup:
        val, key = lookup[t]
        allowed = [str(x).upper() for x in v.get(key, [])]
        req = f"{t.replace('_', ' ').title()}: {', '.join(allowed)}"
        if val is None:
            return RuleResult(**base, outcome="unknown", user_value=None, requirement=req, explanation=f"Add your {t.replace('_', ' ')} to check this.")
        ok = str(val).upper() in allowed
        return RuleResult(**base, outcome="pass" if ok else "fail", user_value=str(val), requirement=req,
                          explanation="Matches." if ok else "This post is limited to other groups.")
    if t == "language":
        lang = str(v.get("required", "")).lower()
        if not p.languages:
            return RuleResult(**base, outcome="unknown", user_value=None, requirement=f"Knowledge of {lang}", explanation="Add the languages you know.")
        ok = lang in p.languages
        return RuleResult(**base, outcome="pass" if ok else "fail", user_value=", ".join(p.languages),
                          requirement=f"Knowledge of {lang}", explanation="Matches." if ok else f"You have not listed {lang}.")
    if t == "attempts":
        slug = v.get("exam_slug", "")
        limits = v.get("by_category", {})
        cat = (p.category or "").upper()
        limit = limits.get(cat, v.get("max")) if cat else None
        used = p.attempts.get(slug)
        req = f"Maximum attempts: {limit if limit is not None else 'depends on category'}"
        if cat == "" or used is None:
            return RuleResult(**base, outcome="unknown", user_value=None if used is None else str(used), requirement=req,
                              explanation="Add your category and attempts used to check this.")
        if limit is None:
            return RuleResult(**base, outcome="pass", user_value=str(used), requirement="No attempt limit for your category",
                              explanation="No limit applies.")
        ok = used < int(limit)
        return RuleResult(**base, outcome="pass" if ok else "fail", user_value=f"{used} used", requirement=req,
                          explanation=f"{int(limit) - used} attempts left." if ok else "You have used all permitted attempts.")
    return RuleResult(**base, outcome="unknown", user_value=None, requirement=v.get("text", t.replace("_", " ")),
                      explanation="This requirement must be checked against the notification.")


def evaluate(rules: list[RuleSpec], profile: Profile) -> Evaluation:
    relax = [r for r in rules if r.rule_type in ("relaxation", "relaxation_reference")]
    results: list[RuleResult] = []
    for r in rules:
        if r.rule_type in ("relaxation", "relaxation_reference"):
            continue
        if r.rule_type == "age":
            results.append(_age_rule(r, profile, relax))
        elif r.rule_type in ("qualification", "qualification_text"):
            results.append(_qual_rule(r, profile))
        else:
            results.append(_simple(r, profile))
    if not results:
        return Evaluation("needs_check", [RuleResult("none", "unknown", None, "No structured rules yet",
                                                     "We have not structured this post's eligibility. Read the notification.")])
    if any(x.outcome == "fail" for x in results):
        status = "not_eligible"
    elif any(x.outcome == "unknown" for x in results):
        status = "needs_check"
    else:
        status = "eligible"
    return Evaluation(status, results)


def countdown(rules: list[RuleSpec], profile: Profile, notification_year: int | None) -> list[dict[str, Any]]:
    """When the user may lose access, projected from the latest official rules. Always labelled as a projection."""
    out: list[dict[str, Any]] = []
    if profile.date_of_birth and notification_year:
        dob = profile.date_of_birth
        for r in rules:
            v = r.params
            if r.rule_type == "age" and v.get("type") == "born_between":
                relax = [x for x in rules if x.rule_type == "relaxation"]
                groups = profile.relaxation_groups()
                years = max((int(x.params.get("years", 0)) for x in relax if str(x.params.get("applies_to", "")).upper() in groups), default=0)
                earliest = _shift_years(date.fromisoformat(v["from"]), -years)
                basis = (f"Projection from the {notification_year} notification's age limit"
                         + (f" with {years} years of relaxation" if years else "")
                         + ". It assumes the same limit each year; future notifications may change it.")
                if dob < earliest:
                    out.append({"kind": "age", "last_year": None, "text": "You are above the upper age limit in the latest notification.",
                                "basis": basis})
                    continue
                # Each yearly notification moves the birth-date window one year later.
                spare = age_on(earliest, dob)
                last = notification_year + spare
                out.append({"kind": "age", "last_year": last,
                            "text": f"You may stay within the upper age limit for notifications up to about {last}.",
                            "basis": basis})
    for r in rules:
        if r.rule_type == "attempts":
            res = _simple(r, profile)
            if res.outcome == "pass" and "left" in res.explanation:
                out.append({"kind": "attempts", "text": res.explanation,
                            "basis": "Based on the latest notification. Future notifications may change this."})
    return out
