"""FastAPI application: public API under /v1, admin console under /admin, health checks, privacy page."""

from pathlib import Path

from examradar_core.db import get_engine
from examradar_core.logging import configure_logging
from examradar_core.settings import get_settings
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import routes_admin, routes_me, routes_public
from .middleware import RequestContext

configure_logging(get_settings().log_level)
REPO = Path(__file__).resolve().parents[3]

app = FastAPI(
    title=f"{get_settings().app_name} API",
    version="1.0.0",
    description="Official Central and Kerala government exam data with evidence. Independent; not affiliated with any government body.",
)
app.add_middleware(RequestContext)
app.include_router(routes_public.router)
app.include_router(routes_me.router)
app.include_router(routes_admin.router)
app.mount("/admin-static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="admin-static")


@app.exception_handler(routes_admin.NeedLogin)
def _need_login(request: Request, exc: Exception):
    return RedirectResponse("/admin/login", status_code=303)


@app.exception_handler(Exception)
def _unhandled(request: Request, exc: Exception):
    import logging

    logging.getLogger("examradar.api").exception("unhandled error", extra={"data": {"path": request.url.path}})
    return JSONResponse({"detail": "Something went wrong. Please try again."}, status_code=500)


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
def readyz():
    with get_engine().connect() as c:
        c.execute(text("select 1"))
    return {"status": "ready"}


@app.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
def privacy():
    p = REPO / "docs" / "privacy-policy.md"
    body = p.read_text(encoding="utf-8") if p.exists() else "Privacy policy not published yet."
    import html

    return HTMLResponse(f"<!doctype html><meta name=viewport content='width=device-width'><title>Privacy</title>"
                        f"<pre style='white-space:pre-wrap;font:15px/1.5 system-ui;max-width:760px;margin:24px auto;padding:0 16px'>"
                        f"{html.escape(body)}</pre>")
