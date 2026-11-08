"""Fetch a user-submitted URL without exposing internal services (SSRF protection).

Every hop is resolved and checked against private, loopback, link-local, multicast, reserved, and carrier-grade NAT
ranges before connecting. Redirects, size, and time are capped. Content is read as bytes and never executed.
Known limitation: a DNS answer could change between our check and httpx's own lookup (rebinding); the window is
small and the response is only parsed as text. See docs/security-review.md.
"""

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

CGNAT = ipaddress.ip_network("100.64.0.0/10")


class UnsafeURL(ValueError):
    pass


@dataclass
class SafeResponse:
    final_url: str
    status: int
    content: bytes
    content_type: str
    hops: list[str]


def _check_host(host: str, port: int) -> None:
    if not host:
        raise UnsafeURL("missing host")
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise UnsafeURL(f"cannot resolve {host}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved
                or ip.is_unspecified or (isinstance(ip, ipaddress.IPv4Address) and ip in CGNAT)):
            raise UnsafeURL("address is not public")


def validate_url(url: str) -> tuple[str, int]:
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise UnsafeURL("only http and https links can be checked")
    if p.username or p.password:
        raise UnsafeURL("links with embedded credentials are not fetched")
    port = p.port or (443 if p.scheme == "https" else 80)
    if port not in (80, 443):
        raise UnsafeURL("only standard ports are fetched")
    _check_host(p.hostname or "", port)
    return p.hostname or "", port


def safe_get(url: str, max_bytes: int = 1_000_000, timeout: float = 8.0, max_redirects: int = 3,
             transport: httpx.BaseTransport | None = None, resolve: bool = True) -> SafeResponse:
    hops = []
    with httpx.Client(timeout=timeout, follow_redirects=False, transport=transport,
                      headers={"User-Agent": "ExamRadar-ScamCheck/0.1"}) as c:
        for _ in range(max_redirects + 1):
            if resolve:
                validate_url(url)
            hops.append(url)
            with c.stream("GET", url) as r:
                if r.is_redirect and r.headers.get("location"):
                    url = urljoin(url, r.headers["location"])
                    continue
                buf, n = [], 0
                for chunk in r.iter_bytes():
                    n += len(chunk)
                    if n > max_bytes:
                        break
                    buf.append(chunk)
                return SafeResponse(str(r.url), r.status_code, b"".join(buf)[:max_bytes], r.headers.get("content-type", ""), hops)
    raise UnsafeURL("too many redirects")
