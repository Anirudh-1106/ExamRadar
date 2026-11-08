from datetime import UTC, date, datetime, time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30), "IST")


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def ist_today() -> date:
    return datetime.now(IST).date()


def end_of_day_ist_as_utc(d: date) -> datetime:
    """A date-only deadline means 23:59:59 IST on that date, stored as naive UTC."""
    local = datetime.combine(d, time(23, 59, 59), tzinfo=IST)
    return local.astimezone(UTC).replace(tzinfo=None)


def to_ist(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(IST)
