# Setup

This file grows with each milestone. As of M0 the repository contains documentation and the source registry only.

## Tools needed for development

| Tool | Version | Status on the current dev machine |
|---|---|---|
| Git | 2.40+ | Installed |
| Python | 3.12 | Python is installed. Confirm a 3.12 interpreter in M1. |
| Docker Desktop with Compose | Current | **Not installed.** Needed from M1 for Postgres, Redis, and MinIO. |
| Flutter SDK | 3.27+ | Installed (3.27.3) |
| Android SDK and platform tools | Current | Platform tools installed |
| Tesseract OCR with `eng` and `mal` | 5.x | Not installed. Runs inside the worker container, so local install is optional. |

## Accounts needed

| Account | Used for | Needed from |
|---|---|---|
| GitHub | Code and CI | Now |
| Groq | Default LLM provider (optional, the system runs without it) | M2 |
| Firebase project | Push notifications (FCM) and optional sign-in | M5 |
| Hosting (VPS or similar) | API, worker, database | Before any public release |
| S3-compatible storage | Document originals and backups | Before any public release |
| Google Play Console | Store listing | M8, only with owner approval |
| Domain name | API and privacy policy URL | Before any public release |

## Environment variables

See `.env.example`. Every variable is listed there with a comment.
