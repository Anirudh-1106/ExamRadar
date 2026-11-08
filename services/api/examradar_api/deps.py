import hashlib
from collections.abc import Iterator
from datetime import date

from examradar_core.db import session_factory
from examradar_core.models import User
from examradar_core.timeutil import ist_today, utcnow
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session


def get_db() -> Iterator[Session]:
    s = session_factory()()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def today() -> date:
    return ist_today()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(authorization: str | None = Header(default=None), s: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Register this device first.")
    u = s.scalar(select(User).where(User.token_hash == token_hash(authorization.split(" ", 1)[1].strip())))
    if u is None:
        raise HTTPException(401, "Unknown device token.")
    u.last_seen_at = utcnow()
    return u


def optional_user(authorization: str | None = Header(default=None), s: Session = Depends(get_db)) -> User | None:
    if not authorization:
        return None
    try:
        return current_user(authorization, s)
    except HTTPException:
        return None
