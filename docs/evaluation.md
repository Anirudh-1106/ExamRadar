# Evaluation

Measured on 2026-11-08. The generated table is in `evaluation-results.md`; rerun with `python tools/evaluate.py`.

## Method

- **Gold set:** `data/gold/labels.yaml`, built from 6 saved official PDFs and 2 listing pages (Kerala PSC, UPSC, IBPS, SBI). It holds 68 labelled facts.
- **Labelling:** every fact was checked against the raw page text of the document, not against extractor output. Labelling was done by the build agent. A human should re-verify it before these numbers are quoted publicly.
- **Scope:** rule extractors only, before validation and admin review. The LLM fallback was not used (no key configured).
- **Matching:** a date counts as correct only if event type, stage, date, precision, and category number all match.

## Results

| Measure | Value |
|---|---|
| Precision, all fields | 100% (65 of 65) |
| Recall, all fields | 95.6% (65 of 68) |
| Extracted facts whose quote was not found in the document | 0 of 149 |

The three misses:

- IBPS result months for the preliminary and main exams. The rules do not extract result dates from schedule tables.
- SBI fee deadline. It is stated jointly with registration ("registration and payment of fees: 11.08.2026 to 31.08.2026"), and the rules treat that as the application window only.

## What these numbers do and do not show

- **The set is small.** 68 facts from 8 documents is far below the brief's target of 200 labelled documents. The 100% precision is encouraging but statistically weak.
- **Bugs found while building the set were fixed first.** Before the fixes, the same documents gave wrong dates: a UPSC start date read as an end date, IBPS result months read as exam months, and a SBI thumb-impression spec copied from the signature spec. The table reflects the fixed rules.
- **Not yet covered:** NTA notices, which are scanned and need OCR; KDRB notice PDFs; RRB section pages, which are firewall-blocked; and Malayalam-only notices.
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
