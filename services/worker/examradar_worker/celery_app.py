"""Celery wiring. Beat runs a five-minute scheduler tick; each source still follows its own interval."""

from celery import Celery
from celery.schedules import crontab
from examradar_core.logging import configure_logging
from examradar_core.settings import get_settings

from . import jobs

configure_logging(get_settings().log_level)
app = Celery("examradar", broker=get_settings().redis_url, backend=None)
app.conf.update(task_acks_late=True, worker_prefetch_multiplier=1, timezone="Asia/Kolkata", task_default_queue="default")


@app.task(name="examradar.crawl_source", autoretry_for=(), max_retries=0)
def crawl_source(source_id: int) -> dict:
    return jobs.crawl_source(source_id)


@app.task(name="examradar.schedule_due")
def schedule_due() -> int:
    ids = jobs.due_source_ids()
    for i in ids:
        crawl_source.delay(i)
    return len(ids)


@app.task(name="examradar.process_documents")
def process_documents() -> int:
    return jobs.process_documents()


@app.task(name="examradar.dispatch")
def dispatch() -> int:
    return jobs.dispatch()


@app.task(name="examradar.reminders")
def reminders() -> int:
    return jobs.reminders()


@app.task(name="examradar.health")
def health() -> int:
    return jobs.health()


@app.task(name="examradar.purge")
def purge() -> int:
    return jobs.purge_scam_text()


app.conf.beat_schedule = {
    "schedule-due": {"task": "examradar.schedule_due", "schedule": 300.0},
    "process-documents": {"task": "examradar.process_documents", "schedule": 300.0},
    "dispatch": {"task": "examradar.dispatch", "schedule": 120.0},
    "reminders": {"task": "examradar.reminders", "schedule": crontab(hour=7, minute=0)},
    "health": {"task": "examradar.health", "schedule": 1800.0},
    "purge": {"task": "examradar.purge", "schedule": 3600.0},
}
