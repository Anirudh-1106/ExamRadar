# Decisions

Each entry records what was decided, why, and when. Entries marked **Open** need the owner's input.

## D1. Monorepo with shared Python packages (2026-11-08)
API and worker share models and extraction code through `packages/`. One repo keeps migrations, adapters, and tests in step.

## D2. Allowlist is data scoped per organisation (2026-11-08)
Recon showed SBI apply links on IBPS hosts and IBPS hosts serving other organisations. An apply link is valid only if its hostname and path prefix are allowlisted for the same organisation as the exam. Entries record who verified them and when.

## D3. Use `www.upsc.gov.in` only (2026-11-08)
`upsc.gov.in` redirects every path to the homepage.

## D4. RRB through the unified site (2026-11-08)
`rrbthiruvananthapuram.gov.in` did not respond. `rrb.indianrailways.gov.in/thiruvananthapuram` serves the same content, organised by CEN and category.

## D5. RBI is manual entry (2026-11-08)
`opportunities.rbi.org.in` serves an image CAPTCHA to automated clients. Bypassing it is forbidden. The admin enters RBI items manually with an official source URL, and source status shows "manual".

## D6. Link to official PDFs instead of re-serving them (2026-11-08)
UPSC and Indian Railways require permission to reproduce material. Stored copies are used internally for evidence and review. Pending legal review.

## D7. English-first evidence for Kerala PSC (2026-11-08)
Malayalam text layers are garbled by legacy fonts. Evidence quotes prefer English text. Malayalam pages are OCR'd when the text layer fails a quality check.

## D8. NTA scope starts with UGC-NET and CSIR-NET (2026-11-08)
Other NTA exams are mostly entrance tests, not government jobs.

## D9. Accounts optional (2026-11-08)
Browsing, saving, and local reminders work without an account. Sign-in is needed only for sync and server push matching. This minimises personal data under the DPDP Act.

## D10. Five bottom tabs for a simple UI (2026-11-08)
Home, Exams, Calendar, My Exams, More. Scam Check, Alerts, Profile, Source status, and About sit under More and are linked from Home where useful.

## D11. SSC is rendered in a headless browser (2026-11-08)
The owner asked for collection from the official sites. SSC's public pages are rendered with Playwright every 3 hours, exactly as a visitor sees them. The internal JSON API is not called. Notice cards open PDFs through click handlers, so items link to the SSC homepage and dates are confirmed by an admin.

## D12. Open: Hosting and accounts
Production needs a host, a domain, and S3-compatible storage. A Firebase project is needed for push, and a Groq key is optional. Until then the backend runs on one machine with SQLite and the single-process scheduler. See `docs/setup.md`.

## D13. UPSC returned HTTP 403 to the crawler (2026-11-08)
During the live run UPSC refused requests carrying our identifying User-Agent, although reconnaissance requests earlier the same day succeeded. The pipeline marks the source "blocked", retries at most once a day, and raises an admin task. I did not change the User-Agent to get around the block. Options for the owner: write to UPSC for permission, or rely on manual entry and news signals for UPSC.

## D14. Supplying a missing intermediate certificate for IBPS (2026-11-08)
`www.ibps.in` sends only its leaf certificate. Instead of turning verification off, `config/extra-ca.pem` adds the GlobalSign GCC R46 OV TLS CA 2025 intermediate, downloaded from the URL in the site's own certificate (SHA-256 D1:60:E2:DE:...:63:F9). It chains to GlobalSign Root R46, which is already trusted. Review it when it expires in June 2029.

## D15. News is collected regularly but shown only as unverified mentions (2026-11-08)
The owner asked for regular updates from newspapers and news, especially for RBI. Publisher RSS feeds (Indian Express Jobs, The Hindu Education, Mathrubhumi) are read hourly. Each headline is stored, shown in a separate "In the news" list labelled "not checked by us", sent to admins as a possible missed notice, and triggers an immediate re-check of the official source. News never creates dates, reminders, eligibility, or links on exam pages. This keeps the brief's rule that published exam data comes only from official sources. Google News feeds exist in the config but are off pending legal review.

## D16. RBI collected from RBI's own RSS plus manual entry (2026-11-08)
`opportunities.rbi.org.in` remains CAPTCHA-protected. RBI's press-release RSS is read for recruitment items, news signals cover the rest, and admins enter dates with an official source URL.

## D17. Drift without code generation (2026-11-08)
The installed Dart SDK (3.7.2) cannot resolve current versions of `drift_dev`. Drift is used through its raw-SQL API, which keeps the offline cache on Drift without a code generator.

## D18. Android minimum version 7.0 (API 24) (2026-11-08)
Required by `firebase_messaging`. That covers nearly all phones in use.

## D19. Changed dates always wait for review (2026-11-08)
A date that differs from an already published one goes to the review queue with priority 1, unless the change upgrades a tentative calendar date to an official notice date. `AUTO_PUBLISH_REVISIONS=true` switches this off for a single-operator setup.

## D20. Mobile API client generated from OpenAPI (2026-11-08)
`tools/gen_dart_models.py` writes typed Dart models from the FastAPI spec. Endpoint calls are a thin hand-written layer in `lib/data/api.dart`. A full generator (openapi-generator) needs Java tooling and produced more code than the app uses.

## D21. UPSC coverage while its site refuses the crawler (2026-11-08)
Checked other routes on 2026-11-08: `upsc.gov.in` still returns 403; `upsconline.gov.in` only previews applications made before 25 March 2025; `upsconline.nic.in` needs a login; PIB's RSS now also returns 403 to the crawler; Employment News' free list had no UPSC items. No other official, openly readable source carries UPSC notices. UPSC updates therefore come from news feeds that allow it (Indian Express Jobs and Education, The Hindu, Mint Education), shown as unverified headlines and raised to admins, who enter official dates from upsc.gov.in in a browser. Disguising the crawler's identity to get past the block was ruled out (brief rule 8).

## D22. OCR from a project-local install (2026-11-09)
Tesseract with English and Malayalam data is installed with conda into `.tools/ocr` (ignored by git), because the system installer needs administrator approval. `TESSERACT_CMD` and `TESSDATA_PREFIX` override the path. Servers install the `tesseract-ocr` and `tesseract-ocr-mal` packages instead. After a rule or OCR change, `examradar reprocess <org>` re-reads stored documents and closes "low text quality" reviews that now read well. A text layer of Latin-looking junk (legacy Malayalam fonts, bad scanner OCR) is detected by its share of oddly shaped tokens and almost no common English words, and is OCR'd instead; on 4,446 stored pages only the K-TET PDFs crossed the threshold.

## D23. One configurable adapter for the later sources (2026-11-09)
CMD Kerala, KTET, Kerala SET, Kerala High Court, KVS, NVS, CTET, ISRO, DRDO, LIC, and EPFO use one generic adapter, set up in `config/sources.yaml`: link rows, tables, or class-based grids, include and exclude patterns, browser rendering where the site needs JavaScript, and age limits on old items. Grid and table entries read only their own cells. `page_dates` reads a key-dates block printed on the listing page and gives it to the latest session, only if the dates fall in that session's year. Each source has a saved fixture and a contract test. A source that needs more than this gets its own adapter.

## D24. Kerala PSC age relaxations come from the official General Conditions (2026-11-09)
The General Conditions page is collected like any other document. Its paragraph 2 concessions become organisation-wide rules, each tagged with its sub-paragraph. A notification's own wording decides which apply: "usual age relaxation" applies all, "Sub paras i, ii ... of Para 2" applies only those, and "including the relaxation as per para 2(i)" removes the community concession that is already in the stated limit. Concessions that depend on facts the app does not ask (for example widows' status) give "check before applying", never a firm yes. The 50-year overall cap is applied last.

## D25. Certificate validity rules (2026-11-09)
Rules such as "OBC certificate issued on or after 01.04.2026" are extracted with their quote and served per exam. The app checks a date the user enters and can set a local reminder. Certificates are never uploaded.

## D26. Only recent news is shown (2026-11-09)
News items from earlier years, or older than 90 days, are skipped at collection and hidden by the API. Old headlines were removed from the live database.

## D27. SQLite in write-ahead mode for local runs (2026-11-09)
Local runs use SQLite with WAL and a 30-second busy timeout, and the pipeline commits after each document, so the API keeps answering while the worker runs. Production uses PostgreSQL.
