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

## D11. Open: SSC collection method
Options: Playwright rendering of public pages, asking SSC for permission to use the JSON API, or manual entry only. Recommended: Playwright every 3 hours with manual fallback.

## D12. Open: Hosting and accounts
Docker is not installed on the development machine. Production needs a host, a domain, a Firebase project, and a Groq API key. See `docs/setup.md`.
