"""Admin authentication: scrypt password hash, TOTP second factor, signed session cookie, CSRF token, lockout."""

import hashlib
import hmac
import os
import secrets
from datetime import timedelta

import pyotp
from examradar_core.models import AdminUser
from examradar_core.settings import get_settings
from examradar_core.timeutil import utcnow
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

SESSION_COOKIE = "er_admin"
SESSION_MAX_AGE = 8 * 3600


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=64)
    return f"scrypt${salt.hex()}${h.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split("$")
    except ValueError:
        return False
    calc = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=64)
    return hmac.compare_digest(calc.hex(), h)


def create_admin(s: Session, email: str, password: str) -> str:
    if len(password) < 12:
        raise ValueError("password must be at least 12 characters")
    secret = pyotp.random_base32()
    s.add(AdminUser(email=email.lower(), password_hash=hash_password(password), totp_secret=secret))
    s.flush()
    return secret


def _ser() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt="admin-session")


def login(s: Session, email: str, password: str, code: str) -> tuple[str | None, str]:
    u = s.scalar(select(AdminUser).where(AdminUser.email == email.lower()))
    now = utcnow()
    if u is None:
        verify_password(password, hash_password("dummy-password-x"))  # equalise timing
        return None, "Invalid credentials."
    if u.locked_until and u.locked_until > now:
        return None, "Account locked. Try again later."
    ok = verify_password(password, u.password_hash) and pyotp.TOTP(u.totp_secret).verify(code, valid_window=1)
    if not ok:
        u.failed_logins += 1
        if u.failed_logins >= 5:
            u.locked_until, u.failed_logins = now + timedelta(minutes=15), 0
        return None, "Invalid credentials."
    u.failed_logins, u.last_login_at, u.totp_confirmed = 0, now, True
    sid = secrets.token_urlsafe(16)
    return _ser().dumps({"uid": u.id, "email": u.email, "sid": sid}), "ok"


def read_session(token: str | None) -> dict | None:
    if not token:
        return None
    try:
        return _ser().loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def csrf_token(session: dict) -> str:
    return hmac.new(get_settings().secret_key.encode(), session["sid"].encode(), hashlib.sha256).hexdigest()


def check_csrf(session: dict, token: str | None) -> bool:
    return bool(token) and hmac.compare_digest(csrf_token(session), token or "")
