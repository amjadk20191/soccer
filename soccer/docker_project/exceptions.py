"""
exceptions.py
─────────────
All custom exceptions for the shamcash scraper.
Catching these lets main.py decide whether to retry, re-login, or abort.
"""


class ShamCashError(Exception):
    """Base class for all scraper errors."""


# ── Auth / session ────────────────────────────────────────────────────────────

class LoginTimeoutError(ShamCashError):
    """QR code was not scanned within the allowed time window."""


class SessionExpiredError(ShamCashError):
    """
    The browser was redirected back to /auth/login during a scrape cycle,
    meaning the server-side session (or refresh token) has expired.
    """


class AuthenticationError(ShamCashError):
    """General failure to authenticate (wrong URL, network error on login, etc.)."""


# ── Scraping ──────────────────────────────────────────────────────────────────

class ScrapingError(ShamCashError):
    """Raised when all fetch strategies fail to return any data."""


class ParseError(ShamCashError):
    """A transaction row could not be parsed into a valid Transaction object."""


# ── Database ──────────────────────────────────────────────────────────────────

class DatabaseError(ShamCashError):
    """Wraps any DB-layer error so the poll loop can handle it uniformly."""


# ── QR server ─────────────────────────────────────────────────────────────────

class QRServerError(ShamCashError):
    """The HTTP server that serves the QR screenshot failed to start or crashed."""
