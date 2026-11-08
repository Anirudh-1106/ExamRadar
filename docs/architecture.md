# Architecture

ExamRadar is a data pipeline with a mobile app on top. The pipeline collects official pages, keeps the originals, extracts facts with evidence, validates them, sends uncertain items to a human, and publishes revisions. The app reads published data, works offline for saved exams, and evaluates eligibility on structured rules.

The product name is configurable in `config/app.yaml` (backend) and `apps/mobile/lib/config/app_config.dart` (mobile). Nothing else hard-codes it.

## Components

```text
                     ┌────────────────────────── services/worker (Celery) ─────────────────────────┐
 Celery Beat ──────► │ schedule ─► fetch ─► normalise+hash ─► store original ─► detect new/changed │
 (per-source config) │                                              │                               │
                     │                              fast alert ◄────┤ (title + official link only) │
                     │                                              ▼                               │
                     │   extract: source rules ─► OCR if needed ─► LLM for remainder (optional)    │
                     │                                              ▼                               │
                     │   validate: dates (IST), ordering, quote-in-text, allowlist, conflicts      │
                     │                       │ pass                     │ low confidence / impact  │
                     │                       ▼                          ▼                          │
                     │                publish revision            review_tasks ─► admin console    │
                     │                       ▼                                                     │
                     │       diff ─► match users ─► notifications (bundled, idempotent) ─► FCM     │
                     └─────────────────────────────────────────────────────────────────────────────┘
                                   │                       │
                              PostgreSQL              Object storage (S3 API, local in dev)
                                   │
                     services/api (FastAPI /v1, admin console with Jinja + HTMX)
                                   │  OpenAPI
                     apps/mobile (Flutter, Riverpod, go_router, Dio, Drift cache)
```

| Path | Role |
|---|---|
| `services/api` | FastAPI app. Public `/v1` API, admin console, OpenAPI spec, Alembic migrations. |
| `services/worker` | Celery tasks and Beat schedule. Crawl, extract, validate, publish, notify. |
| `packages/source_adapters` | One adapter per organisation, plus the shared HTTP client, robots.txt cache, rate limiter, and challenge-page detector. |
| `packages/extraction` | Text and table extraction, OCR, Malayalam normalisation, date parsing, rule extractors, LLM provider abstraction, validators. |
| `packages/eligibility` | Pure-Python deterministic evaluator. No I/O. Shared rule schema used by API and tests. |
| `packages/core` | SQLAlchemy models, Pydantic schemas, settings. Shared by API and worker. |
| `apps/mobile` | Flutter app. |
| `data/fixtures` | Saved real official documents for adapter contract tests, with a manifest of URL, hash, and retrieval time. |
| `data/gold` | Hand-labelled extraction targets for evaluation. |

## Source adapter contract

```python
class SourceAdapter(Protocol):
    key: str                                  # "kerala_psc"
    def discover(self, ctx) -> list[ListingRef]          # listing URLs to check now
    def fetch(self, ref, ctx) -> Snapshot                # via shared polite client only
    def parse_listing(self, snap) -> list[ItemRef]       # notice title, URL, dates shown on listing
    def classify(self, item) -> ItemKind                 # notification, programme, admit card, ...
    def extract(self, doc) -> list[CandidateFact]        # rules only; LLM handled by pipeline
```

- Adapters never make network calls directly. The shared client enforces robots.txt, per-host rate limits, conditional requests (ETag and Last-Modified), backoff with jitter, size and time limits, and a fixed User-Agent.
- A challenge or block page (F5 support ID, CAPTCHA text, HTTP 418 or 403) raises `SourceBlocked`. The source goes to status `blocked` and the admin is alerted. There is no retry storm.
- Each adapter runs in its own task with its own error budget, so one site's layout change cannot break another.
- Adapter contract tests run each adapter against saved fixtures and assert the item list and extracted facts.

## Change detection

1. Normalise HTML: remove scripts, styles, navigation, counters, session tokens, CSRF fields, and timestamps in query strings such as SBI's `?t=`. Keep the main content region chosen by a per-source CSS selector.
2. Hash the normalised content (SHA-256). Same hash means no change.
3. On change, store the raw bytes first, then parse. Parse the listing into items keyed by a stable identity (category number, CEN, advertisement number, or normalised URL).
4. New item on an allowlisted source: publish a **fast alert** with title, organisation, and official link only, no dates.
5. Documents (PDFs) are hashed on bytes. A new hash at the same URL is a new document version.

## Extraction and evidence

- Order: source-specific rules, then table extraction, then OCR for pages whose text fails a quality check, then the LLM for fields still missing.
- Every candidate fact carries: document ID, document hash, page number, exact supporting quote, character offsets, extractor name and version, and confidence.
- Validation rejects a fact if the quote is not found in the stored document text after whitespace and Malayalam normalisation.
- The LLM receives document text as data inside a delimited block, with a strict JSON schema output. Its output is a candidate only. It cannot publish, cannot decide eligibility, and cannot add links.
- If the LLM is down or no key is set, rules still run, fast alerts still go out, and remaining fields become review tasks.

## Dates

- Parsed with explicit Indian formats: `dd/mm/yyyy`, `dd.mm.yyyy`, `dd-mm-yyyy`, `dd Month yyyy`, and Malayalam month names. Never US order.
- Times are stored as UTC with `Asia/Kolkata` as the display zone. A date-only deadline means 23:59:59 IST unless the notice states a time.
- Certainty labels: `official`, `tentative`, `expected`. Only `official` and `tentative` can drive deadline reminders. `expected` is shown as an estimate only.
- Checks: start before end, confirmation before exam, exam after notification, year within a plausible window, and conflicts with other sources for the same event.

## Data model

Migrations in M1 cover all tables named in the brief. Key relationships:

- `organisations` 1─n `sources` 1─n `crawl_runs` 1─n `source_snapshots`. `documents` are stored originals with hash, MIME type, storage key, and text.
- `official_domains`: (organisation, hostname, path prefix, purpose: `content` | `apply` | `portal`, verified_by, verified_at). Apply links must match an entry for the **same organisation**.
- `exams` (family, for example "Kerala PSC LDC") 1─n `exam_cycles` (one notification) 1─n `posts`. `category_numbers` link Kerala PSC categories to cycles and posts. A combined prelims is an exam cycle linked to many category numbers.
- `events` hold the current value per (cycle, event type, scope). `event_revisions` are append-only, with old value, new value, revision time, stated reason, and evidence. Retraction is a revision with status `retracted`.
- `extraction_runs` 1─n `extracted_fields` 1─n `field_evidence`. `review_tasks` point to fields.
- `eligibility_rules` belong to posts and reference `qualification_taxonomy` and `relaxation_rules`, with evidence.
- User tables hold only what features need. `user_profiles` store date of birth, category, qualifications, and Kerala community only after consent, each with a purpose note.
- `notifications` have an idempotency key: hash of (user, event, revision, type, offset). `notification_deliveries` record each channel attempt.

## Notifications

- Triggered by published revisions and by scheduled deadline offsets (7, 3, and 1 days, and confirmation deadlines).
- Matching uses saved exams first, then interest filters, then eligibility results.
- Bundling: one digest per user per window, except urgent deadlines within 24 hours. Quiet hours respected except for urgent deadlines.
- The device schedules local reminders for saved deadlines as a backup to push. They are rescheduled when a revision arrives.
- Every notification carries a deep link such as `examradar://exam/<cycle_id>?tab=changes`.

## Mobile app

- Riverpod for state, go_router for navigation and deep links, Dio with a generated OpenAPI client, Drift for offline cache of saved exams and the last-fetched lists.
- Large tap targets, plain-language labels, and one primary action per screen. Five bottom tabs: Home, Exams, Calendar, My Exams, More.
- Strings live in ARB files from day one. Malayalam is added in M8. Dates, numbers, and links render from structured data, never from translated text.
- Light and dark themes with a restrained palette. No ads and no coaching promotions.
- Document readiness checks (photo size and dimensions, name and DOB matching) run on the device only. Nothing identity-related is uploaded.

## Admin console

Server-rendered Jinja with HTMX inside the API service, under `/admin`. Protected by password plus TOTP, secure session cookies, CSRF tokens, and IP rate limits. Every action writes to an audit log. Screens follow the brief.

## Scam Check

- URL checks: exact match against `official_domains`, lookalike detection (edit distance, homoglyphs, and tricks like `gov.in.example.com`), suspicious patterns (shorteners, free hosting, IP addresses), and domain age through RDAP.
- Text checks: notification numbers and titles searched against our official records, fee and payment signals, UPI handles, and phone-number payment requests.
- Fetching is SSRF-safe: resolve DNS and block private, loopback, link-local, and metadata ranges, re-check after every redirect, at most 3 redirects, 5 MB, and 10 seconds, and never execute content.
- Submitted text is deleted after 24 hours. Only the verdict and evidence summary are kept.
- Verdicts: `Verified on official source`, `Not found on official sources`, `Suspicious`, `Known fake`. The app never says a notice is safe.

## Security and privacy

- TLS everywhere. Secrets come from environment variables, never git. Database encryption at rest is provided by the host.
- Structured JSON logs with request IDs. Profile fields are never logged. A logging filter strips known personal keys.
- Rate limits on public endpoints, stricter limits on Scam Check.
- Accounts are optional. Anonymous device mode works for browsing and local reminders. Sign-in (Firebase Auth, phone or Google) is needed only for sync and push matching.

## Hosting

Docker Compose runs Postgres, Redis, API, worker, Beat, and MinIO locally. For production, a single small VPS (2 vCPU, 4 GB) running the same Compose file is enough at launch, with managed backups to S3-compatible storage. Playwright runs in a separate worker image so the default worker stays small.
