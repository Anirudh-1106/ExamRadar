# Security review

Self-review of the code as of 2026-11-08. An independent review is recommended before public launch.

## Covered

| Area | Control | Tested |
|---|---|---|
| SSRF in Scam Check | Every hop resolved and checked against private, loopback, link-local, multicast, reserved, and CGNAT ranges. Standard ports only. No credentials in URLs. At most 3 redirects, 1 MB, 8 seconds. | `test_ssrf_protection` |
| Untrusted documents | PDFs are parsed with PyMuPDF only. Nothing is executed. The admin view serves stored files with `Content-Security-Policy: sandbox`. Document text is HTML-escaped before highlighting. | Partly (`highlight` escapes) |
| Prompt injection | Document text is passed to the LLM inside delimiters and labelled untrusted. Output must match a schema, every value needs a quote found in the document, and LLM facts always go to human review. | Pipeline tests (no live LLM) |
| Apply links | Exact hostname plus path prefix, scoped to the organisation. Lookalikes and subdomains are rejected. | `test_allowlist_exact_host` |
| Admin access | scrypt password hash, TOTP second factor, 15-minute lockout after 5 failures, signed HttpOnly SameSite=Strict cookie with an 8-hour expiry, CSRF token on every write, audit log. | `test_admin_requires_login_totp_and_csrf` |
| Rate limits | Per client IP and route group, stricter for Scam Check and admin login | Manual |
| Personal data in logs | Access logs record method, path, status, and time only. A scrubber removes known personal keys from structured log data. | Manual |
| Data minimisation | Profile on the phone by default. Scam text purged after 24 hours. Account deletion removes all user rows. | `test_device_profile_saved_status_export_delete`, `test_scam_text_is_purged` |
| TLS to sources | Verification always on. One missing intermediate certificate supplied from the issuing CA. | Live run |
| Secrets | Only in environment variables. `.env`, keystores, and service-account files are git-ignored. | Manual |

## Known gaps

- **DNS rebinding:** a domain could resolve to a public address during our check and a private one when httpx connects. The window is small and responses are only parsed as text. Fix later by pinning the resolved IP in a custom transport.
- **Rate limits are per process.** With several API workers each keeps its own counters. Move them to Redis if abuse appears.
- **Device tokens are bearer tokens.** Losing one exposes that device's saved exams and profile. They are stored in the app's private storage.
- **Cleartext HTTP is allowed in the APK** so it can reach a development server on the local network. Remove it before release.
- **No CAPTCHA on Scam Check.** Rate limiting is the only abuse control.
- **Admin brute force across many IPs** is limited by per-account lockout, not by IP reputation.
- **Dependencies:** run `pip-audit` and `flutter pub outdated` before release. They were not run in this build.
