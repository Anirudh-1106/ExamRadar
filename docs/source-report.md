# Source reconnaissance report

Checked on **2026-11-08** from a connection in India, using plain HTTPS requests with a descriptive User-Agent, no cookies, no login, and no JavaScript. Every observation below comes from pages actually fetched on that date. Anything not checked is marked as such.

## Summary

| Source | Collectable without JS? | Feed / API | robots.txt | Reuse terms | Verdict for launch |
|---|---|---|---|---|---|
| UPSC | Yes (www host only) | None found | None served | Reproduction needs permission. Linking allowed. | **Ready (M1)** |
| Kerala PSC | Yes | None found | Present. Content paths allowed. | Free reproduction if accurate and not misleading | **Ready (M1)** |
| Thulasi | Not collected | n/a | None | n/a | Link target only |
| KDRB | Yes (WordPress) | RSS disabled. Sitemap available. | Present. Content allowed. | Not found | **Ready (M3)** |
| SBI Careers | Yes | None | Allows all | Not found | **Ready (M3)** |
| IBPS | Yes (WordPress) | RSS exists but stale (latest item Jan 2024) | None served | Not found | **Ready (M3)** |
| NTA | Yes | None | None served on nta.ac.in | Not found | **Ready (M3)** |
| RRB (unified site) | Yes | None | Request rejected by firewall | Railways: reproduction needs permission | **Ready with care (M3)** |
| RRB regional sites | No response | n/a | n/a | n/a | Replaced by unified site |
| SSC | **No.** Angular app, empty HTML | Internal JSON API, undocumented | None served | Not found | **Decision needed** |
| RBI recruitment | **No.** Bot challenge with image CAPTCHA | None | Bot challenge | Not found | **Manual entry only** |

## Cross-cutting findings

1. **Domains have moved.** SBI now lives on `sbi.bank.in`, and `sbi.co.in` shows a 5-second redirect page. RRB regional sites did not respond, and RRB content now sits under `rrb.indianrailways.gov.in/<board>`. NTA uses both `nta.ac.in` and `nta.nic.in` families. The allowlist must be maintained data, not code.
2. **Apply links cross organisations.** SBI's apply buttons point to both `recruitment.sbi.bank.in` and `ibpsreg.ibps.in`. IBPS's registration host also serves CWC, NIT, and RSBL recruitments. An allowlist entry therefore means "hostname X is a valid apply host for organisation Y". A link on `ibpsreg.ibps.in` is only valid for an organisation whose own official page points to it.
3. **Apply and call-letter URLs carry tokens.** IBPS and SBI call-letter links include an `appid=` parameter. Store them as published, but match the allowlist on hostname plus path prefix.
4. **All sampled PDFs have text layers.** Six PDFs were tested with PyMuPDF and none needed OCR. OCR is still needed for scanned gazettes and for Malayalam (see Kerala PSC).
5. **Malayalam text layers are unreliable.** Kerala PSC PDFs made with OpenOffice and iLovePDF use legacy font mappings. Extracted Malayalam comes out in visual glyph order, for example `േകരള` instead of `കേരള`, and some lines become unreadable. Rules: take evidence quotes from English text where both exist, normalise Malayalam before matching, and OCR Malayalam pages when the text layer fails a quality check.
6. **Copyright terms differ.** UPSC and Indian Railways require permission to reproduce material. Kerala PSC allows free reproduction if accurate. Every source with a hyperlinking policy allows linking. Plan: show short factual extracts such as dates, fees, and counts, with a link to the official PDF. Keep stored originals for evidence and admin review, not public redistribution. Listed in `legal-review.md`.
7. **Bot defences exist.** RBI recruitment and parts of the RRB site sit behind an F5 web application firewall. The RRB homepage and board pages loaded normally, but `/robots.txt` was rejected. Collection must stay slow, and any challenge page must be detected and treated as "blocked", never retried aggressively.
8. **Timestamps in file names.** NTA notices are named `Notice_YYYYMMDDHHMMSS.pdf`, and SBI file names often start with a date like `04112026_`. These help measure detection latency.

## Per source

### UPSC

- **Official hostnames:** `www.upsc.gov.in` for content. `upsc.gov.in` redirects every path to the homepage, so always use www. `upsconline.gov.in` and `upsconline.nic.in` are application portals (ORA, marks).
- **Listing pages:** `/whats-new`, `/examinations/active-exams`, `/examinations/forthcoming-exams`, `/examinations/exam-calendar`, `/recruitment/recruitment-advertisement`, `/examinations/answer-key`, `/examinations/cutoff-marks--`.
- **Structure:** Drupal, server-rendered. Exam pages are at `/examinations/<URL-encoded exam name>` and link the notice PDF, for example `/sites/default/files/Notif-ESEP-2027-Engl-160926.pdf`.
- **JS:** Not needed. Pages show an "enable JavaScript" banner, but the content is in the HTML.
- **Feeds:** `/rss.xml` redirects to the homepage. No feed.
- **PDFs:** Word-generated with text layers. The ESE 2027 notice (62 pages) has a key-dates block on page 1: notification date, last date, prelims date, and mains date.
- **Update pattern:** Annual calendar. The 2027 calendar was uploaded on 20/05/2026, and the 2025 calendar reached "Revised-III". Notices follow the calendar. What's-new items appear several times a week.
- **Risks:** Calendar revisions are frequent, so calendar dates are `tentative`. Exam pages are keyed by name, which changes each year.
- **Collection:** httpx and BeautifulSoup. Every 2 hours, and every 30 minutes during open application windows.

### Kerala PSC

- **Official hostnames:** `keralapsc.gov.in` and `www.keralapsc.gov.in` for content. `thulasi.psc.kerala.gov.in` is the candidate portal. `psc.kerala.gov.in` hosts the exam marks app. `pscbulletin.kerala.gov.in` is the PSC Bulletin (not checked).
- **Listing pages:**
  - `/notifications` is a table with title "EXTRA ORDINARY GAZETTE DATE dd/mm/yyyy", category number range, and last date. Each row links to a gazette page with one PDF per category number, for example `/sites/default/files/2026-10/noti-162-26.pdf`.
  - `/examinations` holds monthly exam programmes, filterable by year. PDFs are titled either "(FOR SUBMITTING CONFIRMATION)" or "(FINALISED AFTER DATE OF CONFIRMATION)". There are also annual programmes.
  - `/latest` is a typed table (Ranked List, Short List, and so on) with category numbers in titles.
  - Also `/shortlists`, `/rankedlist`, `/interviews`, `/answerkey_omrexams`, `/answerkey_onlineexams`, `/psc-examination-updates`, and `/otv-schedule-and-driving-test`.
- **Structure:** Drupal, server-rendered. No JS needed.
- **robots.txt:** Blocks only admin, search, and user paths. Listing and file paths are allowed.
- **Terms:** The copyright page allows free reproduction if accurate and not misleading.
- **PDFs:**
  - Notification PDFs (iLovePDF) mix English and Malayalam. The opening is English, for example "CATEGORY No. 162/2026 ... Applications are invited online only by One Time Registration".
  - Exam programme PDFs (OpenOffice) contain one wide table per page. PyMuPDF's table finder recovers rows correctly: serial number, category number, post, department, statewide or district, exam date with weekday, admission ticket date, date of confirmation or "Confirmation not required", mode and marks, medium, duration, candidate count, and syllabus link. Spaces inside cells are lost ("ASSISTANTDIRECTOROF") and need repair against the notification title.
  - Date-change notices can be Malayalam-only. The November 2026 rescheduling notice was.
- **Update pattern:** Gazette notifications on the last working day of each month (observed 30/05, 30/06, 30/07, 31/08, 30/09, and 30/10 in 2026). The last date is about 33 to 35 days later. Monthly programmes for confirmation are published about two months ahead.
- **Brief vs reality:** Confirmation deadlines appear as a per-row column in the "for submitting confirmation" programme, not as separate notices. This fits the brief's model. Common preliminary exams group many category numbers.
- **Risks:** Malayalam extraction quality. Table layout may change between months. Date changes can be announced only as a scrolling homepage link to an inline PDF.
- **Collection:** httpx, BeautifulSoup, and PyMuPDF tables. Every 2 hours, and every 30 minutes near month end and near confirmation deadlines.

### Thulasi

- `https://thulasi.psc.kerala.gov.in/` redirects to `/thulasi`, which is a login portal. **Not collected.** Used only as the apply link target, with a copyable category number. No per-category deep link was found.

### KDRB (Kerala Devaswom Recruitment Board)

- **Official hostnames:** `kdrb.kerala.gov.in` is the WordPress information site. `recruitment.kdrb.kerala.gov.in` is the application portal, with candidate login, Aadhaar-based One Time Registration, and a public "Latest Notifications" page at `/index.php/LatestNotifications`.
- **Listing pages:** `/category/examination/notifications/` (105 archive pages), `/category/examination/announcements/`, `/category/answerkery-omrexam/` (spelled that way), `/category/examination/examination-calender/`, `/category/results/ranked-lists/`, `/category/results/short-lists/`, and `/category/press-releases/`.
- **JS:** Not needed.
- **robots.txt:** Blocks only `/wp-admin/`. Publishes `wp-sitemap.xml`, which is a cheap change detector.
- **Feeds:** `/feed/` URLs redirect to the homepage, so RSS is disabled. Use the sitemap for discovery.
- **Risks:** Notices may be images or scans inside posts (not sampled yet). The portal uses Aadhaar for registration. ExamRadar must never ask for Aadhaar.
- **Collection:** Sitemap plus category pages. Every 3 hours.

### SBI Careers

- **Official hostnames:** `sbi.bank.in` with careers at `/web/careers`, `/web/careers/current-openings`, `/web/careers/recruitment-results`, and `/web/careers/recruitment-results-archive`. Apply hosts are `recruitment.sbi.bank.in` and, for some recruitments, `ibpsreg.ibps.in`. `sbi.co.in` is a legacy redirect.
- **Structure:** Liferay, server-rendered, gzip. Each opening lists English and Hindi advertisement PDFs, an apply button with the window in its label ("APPLY ONLINE (04.11.2026 to 25.11.2026)"), biodata forms, corrigenda, interview schedules, and select lists.
- **robots.txt:** Allows everything. Sitemap at `/webfiles/uploads/files_2526/sitemap.xml`.
- **PDFs:** Word-generated with text layers.
- **Update pattern:** Several specialist cadre advertisements per month in September to November 2026. Junior Associates yearly. Extensions appear by editing the apply button label ("Online Registration Extended till 16.11.2026").
- **Risks:** Extensions appear only as label changes, so the listing must be diffed at link-label level. Document URLs carry a changing `?t=` timestamp that must be normalised away.
- **Collection:** httpx. Every 2 hours.

### IBPS

- **Official hostnames:** `www.ibps.in` (WordPress), `ibpsreg.ibps.in` for registration, call letters, and results for IBPS and client organisations, and `cgrs.ibps.in` for grievances. The homepage also links `www4.digialm.com`, a third-party exam vendor. **Do not allowlist digialm.com by default.**
- **Listing pages:** Homepage news, `/index.php/recruitment/`, and `/index.php/careers/`.
- **Feeds:** `/feed/` exists, but its latest items are dummy posts from January 2024. **Not usable.**
- **PDFs:** Word-generated with text layers. The CRP PO/MT-XVI notification is 54 pages.
- **Update pattern:** Annual CRP cycles (PO, SO, Clerk, RRB). The notification for 2027-28 vacancies was published on 30.06.2026. Frequent client recruitments.
- **Risks:** Many IBPS links are for other organisations' recruitments. Classify by organisation, not by host.
- **Collection:** httpx. Every 2 hours.

### RBI

- **Official hostnames:** `www.rbi.org.in` and `rbi.org.in` (main site), `opportunities.rbi.org.in` (recruitment). The main site's "Recruitment related Announcements" link goes to `/Scripts/resultsnew.aspx` on the recruitment host.
- **Finding:** `opportunities.rbi.org.in` returns an F5 bot-defence page with an image CAPTCHA ("What code is in the image?") for `/`, `/Scripts/Vacancies.aspx`, `/Scripts/resultsnew.aspx`, and `/robots.txt`. The main site returns HTTP 418 "Unauthorised Access" for `/robots.txt`.
- **Verdict:** **Cannot be collected automatically without bypassing a CAPTCHA, which the rules forbid.** Use the manual-entry path. Source status shows RBI as "manual", and an admin checks the page in a browser on a schedule.
- **Optional:** Ask RBI for permission or a feed. Listed as a decision.

### RRB

- **Official hostnames:** `rrb.indianrailways.gov.in`, the new unified site for all 21 boards. `rrbthiruvananthapuram.gov.in` and its www variant did not respond over http or https. `www.rrbcdg.gov.in` also did not respond.
- **Structure:** Per-board pages at `/<board>`, for example `/thiruvananthapuram`, with tabs per CEN number and category via `/getdata?cennum=01/2024&loc=thiruvananthapuram&category=Notification`. Categories include Indicative Notice, Notification, Application (Special Notice), City Intimation (Exam), E-Call Letters, Exam Schedule, Exam Results, Objection Tracker, Document Verification, Medical Examination, Selection List, Special Notice on Examination, and Mock Test Link. These map well onto lifecycle events.
- **JS:** Board pages are server-rendered.
- **robots.txt:** Rejected by the firewall ("The requested URL was rejected"). Treated as unknown. Crawl conservatively: at most one request every 10 seconds, every 3 hours, and stop on any rejection page.
- **Terms:** Indian Railways terms require permission to reproduce material.
- **Model note:** CENs are national and repeated across boards. One CEN becomes one exam cycle, with per-board pages as sources.
- **Collection:** httpx. Every 3 hours. Start with Thiruvananthapuram.

### NTA

- **Official hostnames:** `nta.ac.in` and `www.nta.ac.in` (main), `exams.nta.ac.in` and `exams.nta.nic.in` (exam microsites, WordPress), `ugcnet.nta.nic.in`, `csirnet.nta.nic.in`, `jeemain.nta.nic.in`, `neet.nta.nic.in`, `cuet.nta.nic.in`, `cbtc.nta.ac.in`, and `examinationservices.nic.in` (application system).
- **Structure:** The homepage is large (840+ PDF links), with "Read More" links named `/Download/Notice/Notice_YYYYMMDDHHMMSS.pdf`. The exam calendar is at `/Download/Notice/ExamcalendarRevised.pdf`.
- **Relevance:** Most NTA exams are entrance tests. For a government exam app, the relevant ones are **UGC-NET and CSIR-NET** (lecturer and JRF eligibility) plus any recruitment exams NTA runs for ministries. Track UGC-NET and CSIR-NET first.
- **Collection:** httpx. Every 2 hours. Detect new notices by file-name timestamp.

### SSC

- **Official hostnames:** `ssc.gov.in` (the bundle also references `ssc.nic.in` as legacy).
- **Finding:** The homepage HTML contains almost no text (39 characters). It is an Angular single-page app that loads content from an internal JSON API under `https://ssc.gov.in/api/`. Route names in the public JS bundle include notice boards and an examination calendar. The API is undocumented, and I did not call it, because using an undocumented internal API may conflict with the site's intended use.
- **Options:**
  1. Render the public pages in Playwright, as a normal browser would, at low frequency. The brief allows Playwright where required and permitted. robots.txt is not served (404), so it sets no restriction.
  2. Ask SSC for permission to use the JSON endpoints.
  3. Manual entry only.
- **Recommendation:** Option 1, every 3 hours, with manual entry as fallback. **Needs your decision.**
- **Not checked:** SSC regional sites, including the Karnataka-Kerala region that serves Kerala candidates.

## Features the brief assumes that the sources do not support

| Brief assumption | Reality | Plan |
|---|---|---|
| Automatic collection for every launch source | RBI blocks automation with a CAPTCHA. SSC needs JS rendering. | RBI manual. SSC through Playwright, pending approval. |
| RSS or API feeds | None usable. IBPS feed is stale. KDRB feed is disabled. | Listing-page diffing, plus the KDRB and SBI sitemaps. |
| `rrbthiruvananthapuram.gov.in` as a source | Did not respond. Content moved to the unified RRB site. | Use `rrb.indianrailways.gov.in/thiruvananthapuram`. |
| Thulasi deep links per category | None found. | Entry page link plus copyable category number. |
| Malayalam text from PDFs | Text layer often garbled. | Tesseract `mal` OCR, plus English-first evidence. |
| Serving official PDFs from our storage | UPSC and Railways require permission to reproduce. | Link to official PDFs. Keep copies internal. Legal review. |
| Official publication time for latency metrics | Rarely stated in HTML. | Use file-name timestamps where present, otherwise first-seen time, and report the limitation. |
| PIB Fact Check feed | Not checked in M0. | Check in M7. |

## Not yet checked

PSC Bulletin, SSC regional sites, UPSC answer key and cut-off page structures, KDRB notice PDFs, scanned gazette samples, and RRB CEN PDF formats. Each will be sampled when its adapter is built.
