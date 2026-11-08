# Deployment guide

A single small server is enough at launch. Nothing has been deployed yet; this needs the owner's hosting account.

## Server

- A VPS with 2 vCPU, 4 GB RAM, and 40 GB disk, in an Indian region for latency.
- Ubuntu LTS with Docker and the Compose plugin.
- A domain name pointing to the server, for example `api.example.in`.

## Steps

1. Clone the repository and create `.env` from `.env.example`. Set `APP_ENV=production`, a long random `SECRET_KEY`, `POSTGRES_PASSWORD`, S3 credentials, and `APP_BASE_URL=https://api.example.in`.
2. Put a TLS reverse proxy in front of port 8000. Caddy is the simplest (`api.example.in { reverse_proxy localhost:8000 }`), and it obtains certificates automatically.
3. Run `docker compose up -d --build`. The API applies migrations on start.
4. Create the first admin: `docker compose exec api examradar create-admin you@example.com`.
5. Check `https://api.example.in/readyz` and the admin console.
6. Build the app with `--dart-define=API_BASE_URL=https://api.example.in`.

## Backups

- PostgreSQL: a nightly `pg_dump` to S3-compatible storage, keeping 30 days. Example cron job:
  `docker compose exec -T postgres pg_dump -U examradar examradar | gzip | aws s3 cp - s3://BUCKET/backups/$(date +%F).sql.gz`
- Document originals are already in object storage. Enable versioning on the bucket.
- Test a restore once a month.

## Monitoring

- Uptime check on `/readyz` every 5 minutes (any free uptime service).
- The admin overview shows sources needing attention, and source health raises review tasks for failures and unusual silence.
- Logs are structured JSON on stdout. Collect them with the host's log driver, or set `SENTRY_DSN` once an error tracker is chosen.

## Updating

`git pull && docker compose up -d --build`. Migrations run automatically. Roll back by checking out the previous commit and running `alembic downgrade` if a migration changed.
