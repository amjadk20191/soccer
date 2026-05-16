from datetime import date, time
from decimal import Decimal, InvalidOperation

from models import Transaction


# ── private helpers ──────────────────────────────────────────────────────────

def _parse_amount(raw: str) -> tuple[Decimal, str, str]:
    """
    '+200 SYP'  →  (Decimal('200'), 'SYP', '+')
    '-1500 SYP' →  (Decimal('1500'), 'SYP', '-')
    """
    raw       = raw.strip()
    direction = "-" if raw.startswith("-") else "+"
    parts     = raw.lstrip("+-").split()

    try:
        amount = Decimal(parts[0]) if parts else Decimal("0")
    except InvalidOperation:
        amount = Decimal("0")

    currency = parts[1] if len(parts) > 1 else "SYP"
    return amount, currency, direction


def _parse_date_time(raw: str) -> tuple[date, time]:
    """
    '2026-05-15 - 17:48:38' →  (date(2026,5,15), time(17,48,38))
    Falls back to today / midnight on any parse error.
    """
    raw        = raw.strip()
    sep        = " - " if " - " in raw else " "
    parts      = raw.split(sep, 1)
    date_str   = parts[0].strip()
    time_str   = parts[1].strip() if len(parts) > 1 else "00:00:00"

    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        d = date.today()

    try:
        t = time.fromisoformat(time_str)
    except ValueError:
        t = time(0, 0)

    return d, t


# ── public API ───────────────────────────────────────────────────────────────

def build_transaction(raw: dict) -> Transaction | None:
    """
    Convert a raw dict (from the DOM scraper or the API interceptor) into a
    typed, immutable Transaction.  Returns None if tx_id is missing.
    """
    tx_id = raw.get("id", "").strip()
    if not tx_id:
        return None

    amount, currency, direction = _parse_amount(raw.get("amount_raw", ""))
    d, t = _parse_date_time(raw.get("date_raw", ""))

    return Transaction(
        tx_id     = tx_id,
        name      = raw.get("name", "N/A").strip(),
        date      = d,
        time      = t,
        amount    = amount,
        currency  = currency,
        direction = direction,
        notes     = raw.get("notes", "").strip(),
    )
