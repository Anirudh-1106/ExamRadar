# ExamRadar

A verified tracker for Central and Kerala government exams. It collects notices from official websites only, keeps evidence for every date it shows, and tells candidates what to do next and by when.

ExamRadar is independent and not affiliated with any government body. Always confirm details on the linked official source.

## Status

Milestone 0 (source reconnaissance and plan) is complete. See:

- [docs/source-report.md](docs/source-report.md) for what each official source supports
- [docs/architecture.md](docs/architecture.md) for the system design
- [docs/plan.md](docs/plan.md) for the milestone plan and extra features
- [docs/decisions.md](docs/decisions.md) for decisions made and open questions
- [docs/legal-review.md](docs/legal-review.md) for items needing legal review
- [docs/setup.md](docs/setup.md) for tools, accounts, and environment variables

## Layout

```text
apps/mobile/                Flutter app
services/api/               FastAPI API and admin console
services/worker/            Celery jobs
packages/source_adapters/   One adapter per official source
packages/extraction/        PDF, OCR, dates, LLM, validation
packages/eligibility/       Deterministic eligibility engine
config/                     Source registry and app settings
data/fixtures/              Saved real official documents for tests
data/gold/                  Hand-labelled evaluation set
docs/                       Reports and decisions
```
