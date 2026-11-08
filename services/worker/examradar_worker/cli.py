"""Command line: `examradar <command>`. Works without Redis, so the whole system can run on one machine."""

import argparse
import json
import sys
import time

from examradar_core.db import get_engine, session_scope
from examradar_core.logging import configure_logging
from examradar_core.models import Base, Source
from examradar_core.settings import get_settings
from sqlalchemy import select

from . import jobs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="examradar")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db", help="create tables directly (development only; production uses alembic)")
    sub.add_parser("sync", help="load config/sources.yaml into the database")
    c = sub.add_parser("crawl", help="crawl sources now")
    c.add_argument("keys", nargs="*", help="organisation or source keys; empty means all due")
    c.add_argument("--force", action="store_true")
    d = sub.add_parser("process", help="download and extract pending documents")
    d.add_argument("--limit", type=int, default=20)
    sub.add_parser("reminders")
    sub.add_parser("dispatch")
    sub.add_parser("health")
    r = sub.add_parser("run", help="single-process scheduler loop (no Redis needed)")
    r.add_argument("--interval", type=int, default=120)
    r.add_argument("--once", action="store_true")
    a = sub.add_parser("create-admin")
    a.add_argument("email")
    args = ap.parse_args(argv)
    configure_logging(get_settings().log_level)

    if args.cmd == "init-db":
        Base.metadata.create_all(get_engine())
        jobs.sync()
    elif args.cmd == "sync":
        jobs.sync()
    elif args.cmd == "crawl":
        with session_scope() as s:
            q = select(Source).where(Source.enabled.is_(True), Source.kind != "manual")
            srcs = s.scalars(q).all()
            ids = [x.id for x in srcs if not args.keys or any(x.key == k or x.key.startswith(k + ":") or (x.organisation and x.organisation.key == k) for k in args.keys)]
        if not args.keys:
            ids = jobs.due_source_ids()
        for i in ids:
            print(json.dumps(jobs.crawl_source(i, force=args.force), default=str))
    elif args.cmd == "process":
        print(jobs.process_documents(args.limit))
    elif args.cmd == "reminders":
        print(jobs.reminders())
    elif args.cmd == "dispatch":
        print(jobs.dispatch())
    elif args.cmd == "health":
        print(jobs.health())
    elif args.cmd == "run":
        jobs.sync()
        while True:
            out = jobs.tick()
            print(json.dumps({"crawled": len(out["crawled"]), "documents": out["documents"], "dispatched": out["dispatched"]}))
            if args.once:
                break
            time.sleep(args.interval)
    elif args.cmd == "create-admin":
        import getpass

        from examradar_api.admin_auth import create_admin

        pw = getpass.getpass("Password (min 12 chars): ")
        with session_scope() as s:
            secret = create_admin(s, args.email, pw)
        print("Admin created. Add this TOTP secret to your authenticator app:", secret)
    return 0


if __name__ == "__main__":
    sys.exit(main())
