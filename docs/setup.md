# Setup

## What you need

| Tool | Version | Why |
|---|---|---|
| Python | 3.12 | API, worker, extraction |
| Flutter | 3.29 (Dart 3.7) | Mobile app |
| Android SDK | API 35, build-tools 35 | Building the APK |
| PostgreSQL | 16 or 17 | Production database. Development can use SQLite. |
| Redis | 7 | Only for Celery in production. The single-process runner does not need it. |
| Docker with Compose | Current | Optional, for running everything as in production |
| Tesseract with `eng` and `mal` | 5.x | OCR for scanned notices. Installed inside the worker image. |

## Run the backend on one machine (no Docker, no Redis)

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev,postgres]"     # on Linux/macOS: .venv/bin/pip
.venv/Scripts/examradar init-db                      # creates storage/examradar.db (SQLite) and loads config/sources.yaml
.venv/Scripts/examradar crawl kerala_psc sbi ibps    # crawl now (polite: about 5 seconds between requests per site)
.venv/Scripts/examradar process --limit 40           # download and read pending notices
.venv/Scripts/uvicorn examradar_api.main:app --host 0.0.0.0 --port 8000
```

Keep it updating in the background with the single-process scheduler:

```bash
.venv/Scripts/examradar run --interval 120
```

Optional collectors:

```bash
.venv/Scripts/pip install -e ".[browser]" && .venv/Scripts/python -m playwright install chromium   # SSC
.venv/Scripts/pip install -e ".[ocr]"      # plus a Tesseract install with English and Malayalam data
```

## Admin console

```bash
.venv/Scripts/examradar create-admin you@example.com
```

Scan the printed TOTP secret into an authenticator app, then log in at `http://localhost:8000/admin`.

## Use PostgreSQL instead of SQLite

```bash
set DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/examradar
cd services/api && ../../.venv/Scripts/alembic upgrade head
```

## Run everything with Docker

```bash
cp .env.example .env      # fill in SECRET_KEY and passwords
docker compose up --build
```

This starts PostgreSQL, Redis, MinIO, the API (which applies migrations on start), the Celery worker, and Celery Beat.

## Build and install the Android app

```bash
cd apps/mobile
flutter pub get
flutter test
flutter build apk --release --split-per-abi --dart-define=API_BASE_URL=http://YOUR-SERVER:8000
```

The APKs are in `apps/mobile/build/app/outputs/flutter-apk/`. Most phones need `app-arm64-v8a-release.apk`. Older phones need `app-armeabi-v7a-release.apk`.

To test on a phone before the server is hosted:

1. Connect the phone and the computer to the same Wi-Fi.
2. Run the API with `--host 0.0.0.0` and allow port 8000 through the Windows firewall.
3. Build the APK with `API_BASE_URL=http://<computer's Wi-Fi IP>:8000`, or change it later in the app under More, Settings, Server address.
4. Copy the APK to the phone and open it. Android asks to allow installing from this source.

The release APK is signed with the debug key so it installs for testing. A real release key is needed before any store upload (see `docs/play-store-checklist.md`).

## Regenerate the Flutter models after API changes

```bash
.venv/Scripts/python tools/gen_dart_models.py
```

## Screenshots and evaluation

```bash
cd apps/mobile && flutter test --update-goldens --tags screenshots --run-skipped test/screenshots_test.dart
.venv/Scripts/python tools/evaluate.py
```

## Accounts needed, and when

| Account | Needed for | When | Status |
|---|---|---|---|
| GitHub | Code and CI | Now | Done |
| Hosting (a small VPS, 2 vCPU and 4 GB) | Making the app work for anyone outside your Wi-Fi | Before sharing the app | Needed from you |
| Domain name with HTTPS | API address and privacy policy URL | Before sharing the app | Needed from you |
| Firebase project (`google-services.json` and a service account) | Push notifications when the app is closed | When you want push | Needed from you. The app already works without it, using on-device reminders and the in-app inbox. |
| Groq API key | LLM fallback for notices the rules cannot read | Optional | Needed from you if wanted |
| S3-compatible storage | Document originals and backups in production | With hosting | Needed from you |
| Google Play Console | Store listing | Only with your approval | Not started |

## Environment variables

Every variable is listed with a comment in `.env.example`.
