import httpx
import pytest
from examradar_adapters.http import (
    FetchError,
    PoliteClient,
    RobotsDisallowed,
    SourceBlocked,
    looks_like_challenge,
)
from examradar_adapters.normalise import main_text, normalise_url, text_hash


class T(httpx.BaseTransport):
    def __init__(self, routes):
        self.routes, self.seen = routes, []

    def handle_request(self, request):
        self.seen.append((str(request.url), dict(request.headers)))
        status, body, headers = self.routes.get(str(request.url), (404, b"", {}))
        return httpx.Response(status, content=body, headers=headers)


def test_robots_respected():
    t = T({"https://x.gov.in/robots.txt": (200, b"User-agent: *\nDisallow: /private/", {"content-type": "text/plain"}),
           "https://x.gov.in/ok": (200, b"<p>fine</p>", {"content-type": "text/html"})})
    c = PoliteClient(min_delay=0, transport=t)
    assert c.get("https://x.gov.in/ok").status == 200
    with pytest.raises(RobotsDisallowed):
        c.get("https://x.gov.in/private/a")


def test_html_robots_page_means_no_rules():
    t = T({"https://x.gov.in/robots.txt": (200, b"<html>home</html>", {"content-type": "text/html"}),
           "https://x.gov.in/a": (200, b"ok", {})})
    assert PoliteClient(min_delay=0, transport=t).get("https://x.gov.in/a").status == 200


def test_challenge_pages_raise_blocked_without_retry():
    body = b"<html>What code is in the image? Your support ID is: 123</html>"
    t = T({"https://x.gov.in/a": (200, body, {})})
    c = PoliteClient(min_delay=0, transport=t)
    with pytest.raises(SourceBlocked):
        c.get("https://x.gov.in/a")
    assert len([u for u, _ in t.seen if u.endswith("/a")]) == 1
    assert looks_like_challenge(418, b"")


def test_conditional_request_and_user_agent():
    t = T({"https://x.gov.in/a": (304, b"", {})})
    c = PoliteClient(min_delay=0, transport=t, user_agent="ExamRadarBot/test")
    r = c.get("https://x.gov.in/a", etag='"abc"')
    assert r.not_modified
    _, headers = [x for x in t.seen if x[0].endswith("/a")][0]
    assert headers["if-none-match"] == '"abc"' and headers["user-agent"] == "ExamRadarBot/test"


def test_size_limit():
    t = T({"https://x.gov.in/big": (200, b"x" * 2000, {})})
    c = PoliteClient(min_delay=0, transport=t)
    c.max_bytes = 1000
    with pytest.raises(FetchError):
        c.get("https://x.gov.in/big")


def test_normalisation_reduces_false_changes():
    a = normalise_url("https://SBI.bank.in//documents/a.pdf?t=1793788834905")
    b = normalise_url("https://sbi.bank.in/documents/a.pdf?t=1790000000000")
    assert a == b == "https://sbi.bank.in/documents/a.pdf"
    h1 = text_hash(main_text("<body><nav>menu</nav><p>Notice</p><p>Visitors: 1234</p><script>x()</script></body>"))
    h2 = text_hash(main_text("<body><nav>other</nav><p>Notice</p><p>Visitors: 9999</p></body>"))
    assert h1 == h2
