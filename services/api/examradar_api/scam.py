"""Scam Check. Returns one of four verdicts with evidence. It never says a notice is safe."""

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from urllib.parse import urlparse

import httpx
from examradar_adapters.normalise import main_text
from examradar_core.models import (
    CategoryNumber,
    ExamCycle,
    FactCheckItem,
    OfficialDomain,
    Organisation,
    ScamCheck,
    SourceItem,
)
from examradar_core.settings import get_settings
from examradar_core.timeutil import utcnow
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .safe_fetch import UnsafeURL, safe_get

VERIFIED, NOT_FOUND, SUSPICIOUS, KNOWN_FAKE = (
    "Verified on official source", "Not found on official sources", "Suspicious", "Known fake")
DISCLAIMER = ("This check looks for warning signs. It cannot prove that a notice is genuine or safe. "
              "Always confirm on the official website before paying or sharing details.")

SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "cutt.ly", "is.gd", "rb.gy", "shorturl.at", "tiny.cc", "goo.gl", "ow.ly", "t.ly", "s.id"}
FREE_HOSTS = ("blogspot.com", "wordpress.com", "sites.google.com", "weebly.com", "wixsite.com", "netlify.app", "vercel.app",
              "github.io", "web.app", "firebaseapp.com", "000webhostapp.com", "carrd.co", "godaddysites.com", "forms.gle",
              "docs.google.com", "telegra.ph", "notion.site", "linktr.ee")
GOVT_TLDS = (".gov.in", ".nic.in", ".bank.in", ".org.in", ".ac.in", ".edu.in", ".kerala.gov.in")
BRAND_WORDS = ("upsc", "ssc", "keralapsc", "kpsc", "psc", "ibps", "sbi", "rbi", "rrb", "railway", "nta", "kdrb", "devaswom",
               "thulasi", "sarkari", "govtjob", "recruitment")
UPI = re.compile(r"\b[\w.\-]{2,}@(?:ybl|okaxis|oksbi|okhdfcbank|okicici|paytm|upi|apl|ibl|axl|sbi|hdfcbank|icici|kotak|yesbank|"
                 r"fbl|barodampay|airtel|jio|ptyes|ptaxis|pthdfc|ptsbi|waicici|wahdfcbank)\b", re.I)
PAY = re.compile(r"(pay|send|transfer|deposit|remit)\w*\b.{0,50}(rs\.?|₹|inr|rupees)\s*[\d,]+", re.I)
WALLETS = re.compile(r"google ?pay|gpay|phone ?pe|paytm|bhim|upi id|scan (the|this) qr", re.I)
SIGNALS = [
    (re.compile(r"guarantee(d)? (job|selection|placement)|100% (job|selection)", re.I), "Promises a guaranteed job or selection."),
    (re.compile(r"without (any )?(exam|interview|test)|no (written )?(exam|test) required|direct (appointment|selection|joining)", re.I),
     "Offers selection without the usual exam or interview."),
    (re.compile(r"(processing|security|registration|training|joining|verification|caution)\s+(fee|deposit|charges?)", re.I),
     "Asks for a processing, security, training, or joining fee."),
    (re.compile(r"limited (seats|vacancies)|last chance|hurry|within 24 hours|today only", re.I), "Uses urgency to pressure you."),
    (re.compile(r"whats ?app\s*(no\.?|number|on|:)?\s*\+?\d[\d\s-]{8,}", re.I), "Asks you to contact a WhatsApp number."),
    (re.compile(r"[\w.]+@(gmail|yahoo|outlook|hotmail|rediffmail)\.com", re.I), "Uses a personal email address, not an official one."),
]
NOTIF_NUMBERS = [re.compile(p, re.I) for p in (
    r"cat(?:egory)?\.?\s*no\.?\s*:?\s*(\d{1,3})\s*/\s*(\d{4})", r"\bCEN\s*(?:No\.?)?\s*(\d{2})\s*/\s*(\d{4})",
    r"(?:advt|advertisement)\.?\s*no\.?\s*:?\s*([A-Z0-9][A-Z0-9/.\-]{3,40})", r"examination notice no\.?\s*:?\s*([\w/.\-]+)")]


@dataclass
class Evidence:
    level: str  # ok | info | warn | bad
    text: str
    url: str | None = None


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


SECOND_LEVEL = {"co", "gov", "nic", "org", "ac", "net", "edu", "res", "gen", "firm", "ind", "bank", "kerala"}


def registrable(host: str) -> str:
    parts = host.split(".")
    if len(parts) >= 3 and parts[-1] == "in" and parts[-2] in SECOND_LEVEL:
        if parts[-2] == "gov" and len(parts) >= 4 and parts[-3] == "kerala":
            return ".".join(parts[-4:])
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def rdap_age_days(domain: str, client: httpx.Client | None = None) -> int | None:
    try:
        c = client or httpx.Client(timeout=6, follow_redirects=True)
        r = c.get(f"https://rdap.org/domain/{domain}")
        if r.status_code != 200:
            return None
        for e in r.json().get("events", []):
            if e.get("eventAction") == "registration":
                when = datetime.fromisoformat(e["eventDate"].replace("Z", "+00:00")).replace(tzinfo=None)
                return (utcnow() - when).days
    except Exception:
        return None
    return None


class ScamChecker:
    def __init__(self, s: Session, fetch: bool = True, rdap: bool = True, http: httpx.Client | None = None):
        self.s, self.fetch, self.rdap, self.http = s, fetch, rdap, http
        self.domains = [(d.host, s.get(Organisation, d.organisation_id).name) for d in s.scalars(select(OfficialDomain))]

    def url(self, url: str, depth: int = 0) -> list[Evidence]:
        ev: list[Evidence] = []
        url = url.strip()
        if not re.match(r"https?://", url, re.I):
            url = "https://" + url
        p = urlparse(url)
        host = (p.hostname or "").lower().rstrip(".")
        if not host:
            return [Evidence("warn", "This does not look like a web address.")]
        try:
            uhost = host.encode().decode("idna") if host.startswith("xn--") or ".xn--" in host else host
        except UnicodeError:
            uhost = host
        if uhost != host or any(ord(c) > 127 for c in uhost):
            ev.append(Evidence("bad", f"The address uses look-alike characters ({uhost}). Official sites do not."))
        exact = [org for h, org in self.domains if h == host]
        if exact:
            ev.append(Evidence("ok", f"{host} is an official address of {exact[0]} on our verified list.", url))
            if p.scheme == "http":
                ev.append(Evidence("info", "The link uses http, not https. Prefer the https address."))
            return ev
        if re.fullmatch(r"[\d.]+|\[[0-9a-f:]+\]", host):
            ev.append(Evidence("bad", "The link points to a raw IP address instead of an official domain."))
        if host in SHORTENERS:
            ev.append(Evidence("warn", "This is a shortened link, which hides where it really goes."))
            if self.fetch and depth == 0:
                try:
                    r = safe_get(url, max_bytes=50_000)
                    if r.final_url != url:
                        ev.append(Evidence("info", f"The short link leads to {r.final_url}", r.final_url))
                        ev += self.url(r.final_url, depth + 1)
                except (UnsafeURL, httpx.HTTPError):
                    ev.append(Evidence("info", "We could not follow the short link."))
        if any(host == f or host.endswith("." + f) for f in FREE_HOSTS):
            ev.append(Evidence("warn", "This site is on a free website or form service. Official recruitment is not run from these."))
        labels = host.split(".")
        for off, org in self.domains:
            base = off.removeprefix("www.")
            if base in host and not host.endswith(base):
                ev.append(Evidence("bad", f"The address contains '{base}' but is not that site. It may be pretending to be {org}."))
                break
            if levenshtein(host.removeprefix("www."), base) <= 2:
                ev.append(Evidence("bad", f"The address is one or two letters away from the official {base} ({org})."))
                break
        brand = [w for w in BRAND_WORDS if any(w in lab for lab in labels)]
        if brand and not host.endswith(GOVT_TLDS):
            ev.append(Evidence("warn", f"The address uses '{brand[0]}' but is not a government domain."))
        if host.count("-") >= 3 or len(url) > 180 or "@" in p.netloc:
            ev.append(Evidence("warn", "The link has an unusual structure often used in phishing."))
        if self.rdap and depth == 0:
            age = rdap_age_days(registrable(host), self.http)
            if age is not None and age < 180:
                ev.append(Evidence("warn", f"The domain {registrable(host)} was registered about {age} days ago."))
            elif age is not None:
                ev.append(Evidence("info", f"The domain {registrable(host)} was registered about {age // 365} years ago. Age alone does not make it official."))
            else:
                ev.append(Evidence("info", "Registration date for this domain is not available."))
        if self.fetch and depth == 0 and not any(e.level == "bad" for e in ev):
            try:
                r = safe_get(url)
                if "html" in r.content_type or "text" in r.content_type:
                    ev += self.text(main_text(r.content)[:20000], fetched=True)
            except (UnsafeURL, httpx.HTTPError) as e:
                ev.append(Evidence("info", f"We did not open the page ({str(e)[:80]})."))
        ev.append(Evidence("info", "This address is not on our list of official addresses."))
        return ev

    def text(self, text: str, fetched: bool = False) -> list[Evidence]:
        ev: list[Evidence] = []
        t = unicodedata.normalize("NFKC", text)
        for m in UPI.finditer(t):
            ev.append(Evidence("bad", f"Contains a personal UPI payment handle ({m.group(0)}). Official fees are never paid this way."))
            break
        if PAY.search(t) and WALLETS.search(t):
            ev.append(Evidence("bad", "Asks for payment through a wallet or UPI app."))
        for rx, msg in SIGNALS:
            if rx.search(t):
                ev.append(Evidence("warn", msg))
        if not fetched:
            for u in re.findall(r"https?://[^\s<>\"')]+|\b(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:in|com|org|net|xyz|online|site|info)\b(?:/[^\s]*)?", t, re.I)[:5]:
                ev += [Evidence(e.level, e.text, e.url) for e in self.url(u) if e.level != "info" or "official" in e.text]
        ev += self.records(t)
        return ev

    def records(self, t: str) -> list[Evidence]:
        ev = []
        for rx in NOTIF_NUMBERS:
            for m in rx.finditer(t):
                if len(m.groups()) == 2:
                    num = f"{int(m.group(1)):03d}/{m.group(2)}" if "cat" in rx.pattern else f"{m.group(1)}/{m.group(2)}"
                else:
                    num = m.group(1).rstrip(".,")
                cn = self.s.scalar(select(CategoryNumber).where(CategoryNumber.number == num))
                cyc = self.s.get(ExamCycle, cn.exam_cycle_id) if cn and cn.exam_cycle_id else self.s.scalar(
                    select(ExamCycle).where(or_(ExamCycle.notification_number == num, ExamCycle.notification_number.like(f"%{num}%"))))
                if cyc:
                    ev.append(Evidence("ok", f"Number {num} matches an official notice we track: {cyc.title}.", cyc.official_url))
                else:
                    ev.append(Evidence("info", f"Number {num} was not found in the official records we track."))
                break
        first = t.strip().split("\n")[0][:200]
        words = set(re.findall(r"[a-z]{4,}", first.lower()))
        if len(words) >= 4:
            for si in self.s.scalars(select(SourceItem).order_by(SourceItem.first_seen_at.desc()).limit(3000)):
                w = set(re.findall(r"[a-z]{4,}", si.title.lower()))
                if w and len(words & w) / len(words) >= 0.7:
                    ev.append(Evidence("ok", f"The title resembles an official notice: {si.title[:140]}", si.url))
                    break
        low = t.lower()
        for fc in self.s.scalars(select(FactCheckItem)):
            if any(u and u.lower() in low for u in fc.urls or []) or (fc.keywords and all(k.lower() in low for k in fc.keywords)):
                ev.append(Evidence("bad", f"Matches a notice declared fake: {fc.title}", fc.source_url))
                ev[-1].level = "fake"
        return ev

    def pdf(self, data: bytes) -> list[Evidence]:
        import pymupdf

        try:
            doc = pymupdf.open(stream=data, filetype="pdf")
        except Exception:
            return [Evidence("warn", "The file could not be read as a PDF.")]
        text = "\n".join(page.get_text() for page in doc)
        links = {lnk.get("uri") for page in doc for lnk in page.get_links() if lnk.get("uri")}
        ev = self.text(text)
        for u in list(links)[:5]:
            ev += [e for e in self.url(u) if e.level in ("bad", "warn", "ok")]
        meta = doc.metadata or {}
        if meta.get("producer") or meta.get("creator"):
            ev.append(Evidence("info", f"PDF made with {meta.get('creator') or meta.get('producer')}. This alone proves nothing."))
        if not text.strip():
            ev.append(Evidence("info", "The PDF has no readable text (it may be a scan). Fewer checks were possible."))
        return ev


def verdict(ev: list[Evidence]) -> str:
    if any(e.level == "fake" for e in ev):
        return KNOWN_FAKE
    if any(e.level in ("bad", "warn") for e in ev):
        return SUSPICIOUS
    if any(e.level == "ok" for e in ev):
        return VERIFIED
    return NOT_FOUND


def run_check(s: Session, kind: str, value: str | bytes, checker: ScamChecker | None = None) -> dict:
    checker = checker or ScamChecker(s)
    if kind == "url":
        ev = checker.url(str(value))
    elif kind == "text":
        ev = checker.text(str(value))
    else:
        ev = checker.pdf(value if isinstance(value, bytes) else str(value).encode())
    seen, uniq = set(), []
    for e in ev:
        if (e.level, e.text) not in seen:
            seen.add((e.level, e.text))
            uniq.append(e)
    if not any(e.level in ("ok", "bad", "warn", "fake") for e in uniq):
        uniq.append(Evidence("info", "We found no official link, notification number, or title that matches the official "
                                     "records we track, and no common scam signs. That does not make it genuine."))
    v = verdict(uniq)
    raw = value if isinstance(value, bytes) else str(value).encode()
    rec = ScamCheck(input_kind=kind, input_hash=hashlib.sha256(raw).hexdigest(), verdict=v,
                    evidence=[asdict(e) for e in uniq], submitted_text=str(value)[:5000] if kind == "text" else None,
                    purge_after=utcnow() + timedelta(hours=get_settings().scam_text_retention_hours))
    s.add(rec)
    s.flush()
    order = {"fake": 0, "bad": 1, "warn": 2, "ok": 3, "info": 4}
    return {"id": rec.id, "verdict": v, "evidence": [asdict(e) for e in sorted(uniq, key=lambda e: order[e.level])],
            "disclaimer": DISCLAIMER}
