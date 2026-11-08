"""Structured JSON logging. Personal profile fields are stripped before anything is written."""

import contextvars
import json
import logging
import sys

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)

PERSONAL_KEYS = {
    "dob", "date_of_birth", "name", "full_name", "category", "community", "kerala_community",
    "qualifications", "email", "phone", "profile", "password", "token", "fcm_token", "text",
}


def scrub(obj):
    if isinstance(obj, dict):
        return {k: ("[redacted]" if k.lower() in PERSONAL_KEYS else scrub(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    return obj


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid:
            payload["request_id"] = rid
        extra = getattr(record, "data", None)
        if extra:
            payload["data"] = scrub(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        return
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root.handlers = [h]
    root.setLevel(level)
