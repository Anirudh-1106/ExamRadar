# Implementation plan

## Status (2026-11-09)

| Milestone | Status | Notes |
|---|---|---|
| M0 Recon and plan | Done | |
| M1 Foundation, Kerala PSC and UPSC | Done | UPSC adapter works on saved pages, but the live site now returns HTTP 403 to the crawler (decisions D13). |
| M2 Extraction and review | Done | OCR runs locally (English and Malayalam). LLM fallback is untested (no key). Gold set: 307 documents, 924 values, mostly Kerala PSC. |
| M3 All launch sources | Done with limits | SSC rendered; RBI via RSS plus manual; RRB alerts only (section pages firewall-blocked); NTA read with OCR. Eleven later sources added through the generic adapter. |
| M4 Mobile read experience | Done | APK builds. Not yet run on a physical phone or emulator from here. |
| M5 Accounts, tracking, alerts | Done with limits | Push needs a Firebase project. Local reminders and the inbox work without it. |
| M6 Eligibility | Done | Kerala PSC relaxations come from the General Conditions. Concessions that depend on unasked facts return "check before applying". |
| M7 Scam Check and readiness | Done | Certificate-validity rules are extracted for UPSC, IBPS, and SBI notices, with date checks and reminders in the app. |
| M8 Release hardening | Partly | Malayalam needs native review; security review, privacy policy, deployment guide, and Play checklist are drafts. Not deployed or submitted. |

Updated after Milestone 0 reconnaissance (2026-11-08). Each milestone ends with a report covering what changed, how to run it, test results, known limitations, and decisions needed.

## Changes from the original brief

- **RBI** moves to manual entry because its recruitment site serves an image CAPTCHA.
- **SSC** needs a Playwright-rendered collector or manual entry, pending your decision.
- **RRB** uses the unified site `rrb.indianrailways.gov.in`. The regional site did not respond.
- **SBI** uses `sbi.bank.in`.
- **NTA** scope is UGC-NET and CSIR-NET first, since most NTA exams are entrance tests.
- **Official PDFs** are linked, not re-served, because UPSC and Railways require permission to reproduce. Stored copies are for evidence and review.
- **Malayalam** extraction relies on OCR, because Kerala PSC text layers are garbled.

## M1: Foundation and two live sources

- Monorepo layout, Docker Compose (Postgres, Redis, MinIO, API, worker, Beat), settings, and `.env.example`.
- SQLAlchemy models and Alembic migrations for every table in the brief.
- Polite HTTP client: robots.txt cache, per-host rate limits, conditional requests, backoff with jitter, size and time limits, and challenge-page detection.
- Adapter framework and registry, loaded from `config/sources.yaml`.
- Snapshots, normalisation, hashing, and original storage.
- Source health: last success, last new item, error rate, parser yield, and staleness.
- **Kerala PSC adapter:** notifications, gazette pages, exam programmes (both confirmation types), and latest.
- **UPSC adapter:** what's new, active exams, exam pages, and calendar.
- Fast alerts for new items.
- Fixtures from real documents, and adapter contract tests.
- CI: ruff, mypy, pytest, and a migration check.

## M2: Extraction and review

- PyMuPDF text and tables, Tesseract OCR (English and Malayalam), and Malayalam normalisation.
- Indian date parser and validators.
- Rule extractors for Kerala PSC notifications and programmes, and UPSC notices.
- LLM provider abstraction (Groq default, strict JSON), with graceful fallback.
- Evidence capture with quote verification.
- Admin console: login with TOTP, review queue with document and highlighted evidence, approve, edit, reject, audit log, manual entry, and re-crawl.
- Revisions with diffs and retraction.
- Initial gold set of 50 or more labelled documents, and an evaluation script.

## M3: All launch sources

- SBI, IBPS, NTA (UGC-NET, CSIR-NET), RRB (Thiruvananthapuram and national CENs), and KDRB adapters.
- SSC: Playwright collector if approved, otherwise manual entry.
- RBI: manual-entry workflow with a reminder for the admin to check.
- Optional missed-notice check, disabled by default and configurable per site.
- Gold set grown toward 200 documents. Evaluation report with precision and recall by source and field, reported as measured.

## M4: Mobile read experience

- Flutter app: Home, Exams (search and filters), Calendar (month and agenda, clash warnings, device calendar export), Exam detail, Source status, About, Privacy, and Disclaimer.
- Generated API client, offline cache, and official links.
- **Debug APK build** that installs on a phone, with steps in `docs/setup.md`.

## M5: Accounts, tracking, and alerts

- Optional sign-in, profile, and My Exams tracking (interested, applied, confirmed, admit card downloaded, exam taken, result checked).
- FCM push, local reminders, preferences, quiet hours, bundling, idempotency, and deep links.

## M6: Eligibility

- Post-level deterministic evaluator with explanations and clause links.
- Age, cut-off date, relaxations, qualifications and equivalence, appearing candidates, nationality and domicile, attempt limits, and Kerala communities.
- Property tests and table-driven tests with boundary dates.
- Matching, plus age and attempt countdowns labelled as projections.

## M7: Scam Check and readiness

- Scam Check for URL, text, and PDF, with SSRF-safe fetching, RDAP lookups, and PIB Fact Check if a permitted source exists.
- Per-exam checklists from official instructions.
- On-device photo and signature validation against versioned official specs.
- Certificate validity reminders and name and DOB mismatch checks.

## M8: Release hardening

- Malayalam UI, performance on low-end devices, accessibility, security review, monitoring, backups, deployment guide, privacy policy draft, data safety notes, and Play Store checklist.
- Signed release APK and AAB, after your approval.

## Additional features for aspirants

These follow the same rules: official data only, evidence for every fact, and nothing invented. Each is placed in the milestone where its data exists.

| Feature | Why it helps | Milestone |
|---|---|---|
| **Simple mode** with larger text and fewer options | Easier for people who are not comfortable with apps | M4 |
| **"What to do today" card** on Home | One clear next action, such as "Submit confirmation for Cat. 162/2026 by 2 Dec" | M4 |
| **Official syllabus and previous papers links** | Kerala PSC, KDRB, and UPSC publish them. Link only. | M4 |
| **Share official link** to WhatsApp, with the source shown | Counters fake forwards by spreading the real link | M4 |
| **Save official PDF to the phone** from the official URL | Read notices offline on weak networks | M4 |
| **Exam clash warning** for saved exams on the same day | Kerala PSC often schedules several exams close together | M4 |
| **Kerala PSC short list and ranked list watch** by category number | Tells you when a list for your category appears | M5 |
| **One Time Registration reminders** for Thulasi and KDRB profiles | Keeps profiles ready before deadlines. No portal login by the app. | M5 |
| **Fee summary by category** from the notification | Quick view of what you will pay, with evidence | M2/M4 |
| **Vacancy summary by category and district** | Helps decide which posts to apply for | M2/M4 |
| **Age calculator** against each notification's cut-off date | Common question, answered deterministically | M6 |
| **"Exams I can still apply for" filter** | Combines eligibility and open windows | M6 |
| **Document checklist** with an on-device folder | Keeps certificates in one place without uploading them | M7 |
| **Study countdown** to each saved exam date | Simple motivation and planning aid. No coaching content. | M5 |
| **Low-data mode** | Skips images and large downloads on mobile data | M4 |
| **Weekly digest** | One summary instead of many alerts | M5 |

## Risks

- Sites change layout without notice. Mitigated by per-source health alerts and contract tests.
- Firewalls may start blocking us. Mitigated by slow crawling and the manual path.
- The 99% precision target depends on review capacity. Numbers will be reported as measured.
- Malayalam OCR quality is unknown until tested on more samples.
