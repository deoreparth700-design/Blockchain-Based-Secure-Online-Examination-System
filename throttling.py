"""
throttling.py
-------------
Database-backed login attempt throttling to protect against brute-force attacks.
Works in serverless environments (e.g. Vercel) where in-memory state does not persist.

Rules:
- 5 failed logins within the last 15 minutes for the same identifier (username/PRN, lowercased)
  blocks further attempts for that identifier until the oldest of those 5 failures is 15 minutes old.
- Successful login clears recorded failures for that identifier.
- Delete failure rows older than 24h whenever a failure is recorded.
"""

import math
from datetime import datetime, timedelta

from models import db, LoginAttempt

WINDOW_MINUTES = 15
MAX_FAILURES = 5
PRUNE_HOURS = 24


class ThrottlingStatus:
    """Helper representing throttling state with boolean, tuple, and attribute compatibility."""

    def __init__(self, blocked: bool, minutes: int = 0):
        self.blocked = blocked
        self.minutes = minutes

    def __bool__(self):
        return self.blocked

    def __iter__(self):
        return iter((self.blocked, self.minutes))

    def __getitem__(self, index):
        return (self.blocked, self.minutes)[index]

    def __repr__(self):
        return f"<ThrottlingStatus blocked={self.blocked} minutes={self.minutes}>"


def normalize_identifier(identifier):
    """Normalize identifier by stripping whitespace and converting to lowercase."""
    return (identifier or "").strip().lower()


def is_blocked(identifier, now=None):
    """
    Check if an identifier is currently blocked due to repeated failed logins.

    Returns:
        ThrottlingStatus: blocked=True/False, minutes=int
    """
    ident = normalize_identifier(identifier)
    if not ident:
        return ThrottlingStatus(False, 0)

    if now is None:
        now = datetime.now()

    window_start = now - timedelta(minutes=WINDOW_MINUTES)

    # Query recent failed attempts in the last 15 minutes, ordered newest first
    recent_failures = (
        LoginAttempt.query.filter(
            LoginAttempt.identifier == ident,
            LoginAttempt.created_at >= window_start,
        )
        .order_by(LoginAttempt.created_at.desc())
        .all()
    )

    if len(recent_failures) < MAX_FAILURES:
        return ThrottlingStatus(False, 0)

    # The block lasts until the 5th most recent failure is 15 minutes old
    threshold_failure = recent_failures[MAX_FAILURES - 1]
    expiry_time = threshold_failure.created_at + timedelta(minutes=WINDOW_MINUTES)
    remaining_seconds = (expiry_time - now).total_seconds()

    if remaining_seconds <= 0:
        return ThrottlingStatus(False, 0)

    minutes_remaining = max(1, int(math.ceil(remaining_seconds / 60.0)))
    return ThrottlingStatus(True, minutes_remaining)


def record_failure(identifier, ip_address=None, now=None):
    """
    Record a failed login attempt for the given identifier.
    Prunes attempts older than 24h to prevent table growth.
    """
    ident = normalize_identifier(identifier)
    if not ident:
        return

    if now is None:
        now = datetime.now()

    # Prune rows older than 24 hours
    cutoff = now - timedelta(hours=PRUNE_HOURS)
    try:
        LoginAttempt.query.filter(LoginAttempt.created_at < cutoff).delete(synchronize_session="fetch")

        attempt = LoginAttempt(
            identifier=ident,
            ip_address=ip_address,
            created_at=now,
        )
        db.session.add(attempt)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def clear_failures(identifier):
    """
    Clear all recorded login failures for an identifier upon successful authentication.
    """
    ident = normalize_identifier(identifier)
    if not ident:
        return

    try:
        LoginAttempt.query.filter(LoginAttempt.identifier == ident).delete(synchronize_session="fetch")
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
