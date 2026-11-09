# Evaluation

Measured on 2026-11-09. The generated table is in `evaluation-results.md`; rerun with `python tools/evaluate.py`.

## Method

- **Detailed gold set:** `data/gold/labels.yaml`, built from 6 saved official PDFs and 2 listing pages (Kerala PSC, UPSC, IBPS, SBI). Dates, age limits, notification numbers, vacancies, photo specs, and certificate rules are labelled field by field.
- **Bulk gold set:** `data/gold/bulk-kerala-psc.yaml`, 299 official Kerala PSC notification PDFs, each identified by URL and SHA-256. Four fields are labelled per document: category number, last date, age limit, and vacancies.
- **How the bulk labels were made:** `tools/gold_helper.py` proposes values from the raw page text with plain date parsing. It does not use the extraction rules. Every row was then checked against its raw snippet, and every category number against the number in the file name. Fields the helper could not read are left out.
- **Who labelled:** the build agent, on 2026-11-08 and 2026-11-09. A human should re-check a sample before these numbers are quoted publicly.
- **Scope:** rule extractors only, before validation and admin review. The LLM fallback was not used (no key configured).
- **Matching:** in the detailed set, a date counts only if event type, stage, date, precision, and category number all match. In the bulk set, a field is correct if the labelled value is among the extracted values.

## Results (2026-11-09)

| Measure | Value |
|---|---|
| Documents scored | 307 (299 bulk, 8 detailed) |
| Labelled values | 924 |
| Precision, all fields | 100% |
| Recall, all fields | 100% |
| Extracted facts whose quote was not found in the document | 0 of 1,729 |

## Bugs the bulk set found, now fixed

- **Spaced category numbers.** Some PDFs print "3 61 /2025". The rule read this as 061/2025 instead of 361/2025 in 37 documents.
- **Trailing dot in dates.** "born between 02.01.1980. and 01.01.2005." gave no age rule in 2 documents.
- **Evidence across a page break.** Qualification and age-relaxation clauses that ran onto the next page failed quote verification in 55 documents. The quote is now cut to the words on one page, and the full text stays in the value.

The earlier misses on the detailed set, IBPS result months and the SBI fee deadline, were fixed on 2026-11-08.

## What these numbers do and do not show

- **The bulk set is one source with one layout.** Kerala PSC notifications follow a fixed clause format, so 100% there says little about other sources. The detailed set covers UPSC, IBPS, and SBI, but with only a few documents each.
- **The helper and the rules read the same extracted text.** A PDF text-extraction fault would affect both and would not show up as a miss. The file-name check guards category numbers against this; the other fields have no second source.
- **Not yet covered:** NTA scanned notices (OCR now reads 45 of 46), KDRB notice PDFs, RRB section pages (firewall-blocked), the later sources added on 2026-11-09, and Malayalam-only notices.
- **The 99% target applies to published dates after review.** Rule facts below confidence 0.85, all LLM facts, and every changed date go to the review queue, so published precision should be at least the raw precision here.

## Live run, 2026-11-08

| Source | Result |
|---|---|
| Kerala PSC | 36 listing items, 908 exam cycles, about 1,536 dates published with evidence |
| SBI | 102 items, 17 dates |
| IBPS | 8 items, after the certificate fix |
| NTA | 145 notices, mostly scanned. Low text quality sent them to review. |
| KDRB | 20 items |
| RRB Thiruvananthapuram | 254 notification-number sections, as alerts without dates |
| SSC | 10 dated notices from the rendered notice board |
| UPSC | Blocked (HTTP 403). No data collected automatically. |
| RBI | RSS readable, no recruitment items that day. Manual entry. |
| News feeds | 69 headlines, 53 sent to admins as possible missed notices |

## Detection latency

Not measurable yet. Latency needs the system to run continuously, so that it sees notices appear. On a first crawl everything is old, so `/v1/stats/latency` currently reports the age of existing notices, not detection speed. NTA and SBI file names carry publication timestamps, so once the scheduler runs for a few weeks the API will report a real median.
