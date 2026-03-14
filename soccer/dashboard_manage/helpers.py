from .models import Club
from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
import datetime
from collections import Counter, defaultdict
from django.db.models import Q
from .models import ClubOpeningTimeHistory, ClubPricing


# ─────────────────────────────────────────────────────────────
# Internal constants
# ─────────────────────────────────────────────────────────────



def _to_club_weekday(python_weekday: int) -> int:
    """
    Python date.weekday(): MO=0 … SU=6
    Club day_of_week:      SA=0, SU=1, MO=2 … FR=6
    """
    return (python_weekday + 2) % 7


# ─────────────────────────────────────────────────────────────
# Helper — build {date: (open_time, close_time)}
# ─────────────────────────────────────────────────────────────

def _build_opening_map(club_id, date_from, date_to):
    """
    Returns dict[date, (open_time, close_time)] for every date in the range.

    Priority (highest wins):
      1. ClubPricing type=2  — specific date override
      2. ClubPricing type=1  — weekday override (repeats weekly)
      3. ClubOpeningTimeHistory — base club hours (may change mid-range)

    DB hits: 2
      • ClubOpeningTimeHistory
      • ClubPricing — ONE query for both types, split in Python
    """

    # ── Query 1: base opening-time history ───────────────────────────────
    history = list(
        ClubOpeningTimeHistory.objects
        .filter(club_id=club_id, created_at__lte=date_to)
        .order_by("created_at")
        .values("created_at", "open_time", "close_time")
    )

    # ── Query 2: ALL pricing exceptions — one shot, split in Python ───────
    # Q(type=1) has no date filter (weekday rules repeat forever).
    # Q(type=2) is scoped to the report window — no point fetching others.
    pricing_rows = ClubPricing.objects.filter(
        Q(club_id=club_id, type=1) |
        Q(club_id=club_id, type=2, date__gte=date_from, date__lte=date_to)
    ).values("type", "day_of_week", "date", "start_time", "end_time")

    weekday_exceptions: dict[int, tuple]          = {}
    date_exceptions:    dict[datetime.date, tuple] = {}

    for row in pricing_rows:
        start, end = row["start_time"], row["end_time"]
        if row["type"] == 1:
            dow = row["day_of_week"]
            if dow not in weekday_exceptions:
                weekday_exceptions[dow] = (start, end)
            else:
                ex_s, ex_e = weekday_exceptions[dow]
                weekday_exceptions[dow] = (ex_s, ex_e)
        else:
            d = row["date"]
            if d not in date_exceptions:
                date_exceptions[d] = (start, end)
            else:
                ex_s, ex_e = date_exceptions[d]
                date_exceptions[d] = (ex_s, ex_e)

    # ── Seed base window — single pass, track index inline ───────────────
    current_open  = None
    current_close = None
    history_idx   = 0

    for i, entry in enumerate(history):
        if entry["created_at"] <= date_from:
            current_open  = entry["open_time"]
            current_close = entry["close_time"]
            history_idx   = i + 1   # next entry to check starts here
        else:
            break

    # ── Walk every date in the range ─────────────────────────────────────
    opening_map: dict[datetime.date, tuple] = {}
    total_days = (date_to - date_from).days + 1

    for day_offset in range(total_days):
        current_date = date_from + datetime.timedelta(days=day_offset)

        # Advance base window if a newer history entry applies.
        while history_idx < len(history):
            if history[history_idx]["created_at"] <= current_date:
                current_open  = history[history_idx]["open_time"]
                current_close = history[history_idx]["close_time"]
                history_idx  += 1
            else:
                break

        if current_open is None:
            continue   # no history at all yet — skip this date

        # Layer 1 — base from history.
        open_t, close_t = current_open, current_close

        # Layer 2 — weekday override.
        club_dow = _to_club_weekday(current_date.weekday())
        if club_dow in weekday_exceptions:
            open_t, close_t = weekday_exceptions[club_dow]

        # Layer 3 — specific-date override (highest priority).
        if current_date in date_exceptions:
            open_t, close_t = date_exceptions[current_date]

        opening_map[current_date] = (open_t, close_t)

    return opening_map


# ─────────────────────────────────────────────────────────────
# Helper — available minutes per hour slot across the range
# ─────────────────────────────────────────────────────────────

def _available_minutes_per_hour(opening_map: dict) -> dict:
    """
    Returns dict[hour (int), total_available_minutes (int)].

    Complexity: O(unique_windows × 24)  —  NOT O(days × 24).

    Most clubs have 2-4 distinct opening windows across a date range.
    Grouping by unique (open_t, close_t) with Counter means we compute
    the 24-slot overlap once per unique window and scale by day_count,
    instead of recomputing it identically for every day.

    Example: 365-day range, 2 distinct windows
      Before: 365 × 24 = 8 760 iterations
      After:    2 × 24 =    48 iterations
    """
    # {(open_t, close_t): number_of_days_sharing_this_window}
    window_counts: Counter = Counter(opening_map.values())

    available: dict = defaultdict(int)

    for (open_t, close_t), day_count in window_counts.items():
        open_minutes  = open_t.hour  * 60 + open_t.minute
        close_minutes = close_t.hour * 60 + close_t.minute

        for hour in range(24):
            slot_start = hour * 60
            slot_end   = slot_start + 60
            overlap    = max(0, min(slot_end, close_minutes) - max(slot_start, open_minutes))
            if overlap:
                available[hour] += overlap * day_count   # scale by day count

    return available

def _parse_date_range(request):
    """
    Parses ?date_from and ?date_to from the request.
    Returns (date_from, date_to) as datetime.date objects.
    Raises ValidationError with a clear message on any problem.
    """
    raw_from = request.query_params.get("date_from")
    raw_to   = request.query_params.get("date_to")

    if not raw_from or not raw_to:
        raise ValidationError(
            {"detail": "Both date_from and date_to are required (YYYY-MM-DD)."}
        )

    try:
        date_from = date.fromisoformat(raw_from)
        date_to   = date.fromisoformat(raw_to)
    except ValueError:
        raise ValidationError(
            {"detail": "Invalid date format. Use YYYY-MM-DD."}
        )

    if date_from > date_to:
        raise ValidationError(
            {"detail": "date_from must be on or before date_to."}
        )

    return date_from, date_to


def _get_club(request):
    """
    Returns the Club that belongs to the authenticated user.
    Raises Http404 if the user has no club.
    """
    return get_object_or_404(Club, manager=request.user)


def _decimal(value):
    """Ensures a None aggregate becomes 0.00 instead of null in JSON."""
    from decimal import Decimal
    return value if value is not None else Decimal("0.00")


def _int(value):
    return value if value is not None else 0

