# services/ClubRevenueService.py

from decimal import Decimal
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from django.db.models import Sum, Count, Q, Case, When, Value, DecimalField
from django.db.models.functions import Coalesce

from player_booking.models import Booking, BookingStatus, PayStatus
from core.models import SyrianGovernorate


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

REVENUE_STATUSES = [
    BookingStatus.PENDING_PAY,
    BookingStatus.COMPLETED,
    BookingStatus.NO_SHOW,
    BookingStatus.DISPUTED,
]

ONLINE_PAY_STATUSES = [
    PayStatus.ONLINE,
    PayStatus.DEPOSIT_ONLINE,
]

# Pre-built label map — avoids BookingStatus(value).label on every row
STATUS_LABEL: dict[int, str] = {
    s.value: str(s.label) for s in REVENUE_STATUSES
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _empty_club(club_id, name, governorate) -> dict:
    return {
        'club_id':       club_id,
        'club_name':     name,
        'governorate':   governorate,
        'total_revenue': Decimal('0'),
        'booking_count': 0,
        'by_status': {
            str(BookingStatus.PENDING_PAY.label): Decimal('0'),
            str(BookingStatus.COMPLETED.label):   Decimal('0'),
            str(BookingStatus.NO_SHOW.label):     Decimal('0'),
            str(BookingStatus.DISPUTED.label):    Decimal('0'),
        },
    }


def _calc_revenue_from_row(row: dict) -> Decimal:
    """
    Pure-dict revenue calculation — no ORM object, no attribute lookup overhead.
    Called only for global-coupon rows (minority path).
    """
    pay    = row['payment_status']
    final  = row['final_price']  or Decimal('0')
    dtype  = row['coupon__discount_type']
    dvalue = row['coupon__discount_value'] or Decimal('0')

    if pay == PayStatus.DEPOSIT_ONLINE:
        deposit = row['deposit'] or Decimal('0')
        # Global coupon: club gets deposit + app-covered portion
        if dtype == 'percentage':
            original       = final / (1 - dvalue / 100)
            discount_share = original * (dvalue / 100)
        else:
            discount_share = dvalue
        return deposit + discount_share

    if pay == PayStatus.ONLINE:
        # Global coupon: reverse discount to recover original price
        if dtype == 'percentage':
            return final / (1 - dvalue / 100)
        return final + dvalue

    return Decimal('0')


def _base_filter(date_from, date_to, club_name, governorate):
    """
    Shared filter dict — applied identically to both queries.
    Using a dict avoids re-constructing Q objects twice.
    """
    f: dict = {
        'status__in':         REVENUE_STATUSES,
        'payment_status__in': ONLINE_PAY_STATUSES,
        'date__range':        (date_from, date_to),
    }
    if club_name:
        f['club__name__icontains'] = club_name.strip()
    if governorate is not None:
        f['club__governorate'] = governorate
    return f


# ─────────────────────────────────────────────────────────────────────────────
# Path A — SQL GROUP BY (standard rows: no coupon + club coupon)
# ─────────────────────────────────────────────────────────────────────────────

def _run_path_a(date_from, date_to, club_name, governorate) -> dict:
    """
    Single aggregation query — the DB sums everything, Python only
    assembles the result dict (one iteration over grouped rows).
    """
    rows = (
        Booking.objects
        .filter(
            **_base_filter(date_from, date_to, club_name, governorate),
        )
        .filter(
            Q(coupon__isnull=True) | Q(coupon__club_id__isnull=False)
        )
        .annotate(
            row_revenue=Case(
                When(payment_status=PayStatus.DEPOSIT_ONLINE, then='deposit'),
                When(payment_status=PayStatus.ONLINE,         then='final_price'),
                default=Value(Decimal('0')),
                output_field=DecimalField(),
            )
        )
        .values('club_id', 'club__name', 'club__governorate', 'status')
        .annotate(
            status_revenue=Coalesce(Sum('row_revenue'), Decimal('0')),
            status_count=Count('id'),
        )
        .order_by()   # required — clears default ordering before GROUP BY
    )

    clubs: dict[str, dict] = {}

    for row in rows:
        cid = str(row['club_id'])

        if cid not in clubs:
            clubs[cid] = _empty_club(cid, row['club__name'], row['club__governorate'])

        label = STATUS_LABEL[row['status']]
        rev   = row['status_revenue']

        clubs[cid]['total_revenue']         += rev
        clubs[cid]['booking_count']         += row['status_count']
        clubs[cid]['by_status'][label]      += rev

    return clubs


# ─────────────────────────────────────────────────────────────────────────────
# Path B — values() dict loop (global coupon rows only)
# ─────────────────────────────────────────────────────────────────────────────

def _run_path_b(date_from, date_to, club_name, governorate) -> dict:
    """
    Uses .values() instead of model instances — eliminates Python object
    instantiation entirely. Coupon fields are joined at DB level so there
    is still only 1 query, no select_related overhead.
    """
    rows = (
        Booking.objects
        .filter(
            **_base_filter(date_from, date_to, club_name, governorate),
            coupon__isnull=False,
            coupon__club_id__isnull=True,    # global coupon only
        )
        .values(
            'club_id',
            'club__name',
            'club__governorate',
            'status',
            'final_price',
            'deposit',
            'payment_status',
            'coupon__discount_type',
            'coupon__discount_value',
        )
        # .iterator() streams rows — avoids loading all into memory at once
        # chunk_size controls how many rows are fetched per DB round-trip
    )

    clubs: dict[str, dict] = {}

    for row in rows.iterator(chunk_size=500):
        cid = str(row['club_id'])

        if cid not in clubs:
            clubs[cid] = _empty_club(cid, row['club__name'], row['club__governorate'])

        rev   = _calc_revenue_from_row(row)
        label = STATUS_LABEL[row['status']]

        clubs[cid]['total_revenue']    += rev
        clubs[cid]['booking_count']    += 1
        clubs[cid]['by_status'][label] += rev

    return clubs


# ─────────────────────────────────────────────────────────────────────────────
# Merge helper
# ─────────────────────────────────────────────────────────────────────────────

def _merge_into(base: dict, extra: dict) -> None:
    """
    Merges extra into base in-place.
    A club that exists only in extra (global-coupon-only club) is added.
    A club in both gets its numbers summed.
    """
    for cid, extra_club in extra.items():
        if cid not in base:
            base[cid] = extra_club
            continue

        base[cid]['total_revenue'] += extra_club['total_revenue']
        base[cid]['booking_count'] += extra_club['booking_count']

        for label, amount in extra_club['by_status'].items():
            base[cid]['by_status'][label] += amount


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_clubs_revenue(
    date_from,
    date_to,
    *,
    club_name:   str | None = None,
    governorate: int | None = None,
) -> list[dict]:
    """
    Returns a list of dicts — one per club — sorted by total_revenue DESC.

    Performance:
      - 2 independent DB queries run in PARALLEL via ThreadPoolExecutor
      - Path A: pure SQL aggregation  — no Python loop over raw rows
      - Path B: .values() dict loop   — no ORM object instantiation
      - STATUS_LABEL pre-built dict   — no enum lookup per row
      - Results merged and sorted in O(n) Python

    Recommended DB indexes (add if not present):
        Booking: (status, payment_status, date)
        Booking: (club_id)
        Booking: (coupon_id)
    """
    args = (date_from, date_to, club_name, governorate)

    # Run Path A and Path B concurrently — they are fully independent queries.
    # ThreadPoolExecutor releases the GIL during DB I/O, so both queries
    # are in-flight at the same time. Wall time ≈ max(A, B) instead of A + B.
    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(_run_path_a, *args)
        future_b = pool.submit(_run_path_b, *args)

        clubs_a = future_a.result()   # blocks until Path A done
        clubs_b = future_b.result()   # blocks until Path B done

    # Merge global-coupon results into the main dict
    _merge_into(clubs_a, clubs_b)

    # Format governorate label once per club — not per booking
    results = []
    for club in clubs_a.values():
        gov = club['governorate']
        club['governorate'] = (
            SyrianGovernorate(gov).label if gov is not None else None
        )
        results.append(club)

    return sorted(results, key=lambda x: x['total_revenue'], reverse=True)