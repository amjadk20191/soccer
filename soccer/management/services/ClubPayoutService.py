from decimal import Decimal
from django.db.models import Sum, Case, When, Value, DecimalField
from django.db.models.functions import Coalesce
from concurrent.futures import ThreadPoolExecutor

from player_booking.models import Booking, BookingStatus, PayStatus
from management.models import ClubPayout
from core.models import SyrianGovernorate
from rest_framework.exceptions import ValidationError

REVENUE_STATUSES = [
    BookingStatus.PENDING_PAY,
    BookingStatus.COMPLETED,
    BookingStatus.NO_SHOW,
    BookingStatus.DISPUTED,
]
ONLINE_PAY_STATUSES = [PayStatus.ONLINE, PayStatus.DEPOSIT_ONLINE]


# ─────────────────────────────────────────────────────────────────────────────
# Path A — collected per club (unchanged, already optimal)
# ─────────────────────────────────────────────────────────────────────────────

def _collected_per_club(club_name, governorate) -> dict[str, dict]:
    qs = (
        Booking.objects
        .filter(
            status__in=REVENUE_STATUSES,
            payment_status__in=ONLINE_PAY_STATUSES,
        )
        .annotate(
            row_revenue=Case(
                When(payment_status=PayStatus.DEPOSIT_ONLINE, then='deposit'),
                When(payment_status=PayStatus.ONLINE,         then='final_price'),
                default=Value(Decimal('0')),
                output_field=DecimalField(),
            )
        )
    )

    if club_name:
        qs = qs.filter(club__name__icontains=club_name.strip())
    if governorate is not None:
        qs = qs.filter(club__governorate=governorate)

    rows = (
        qs
        .values('club_id', 'club__name', 'club__governorate')
        .annotate(total_collected=Coalesce(Sum('row_revenue'), Decimal('0')))
        .order_by()
    )

    return {
        str(r['club_id']): {
            'club_name':       r['club__name'],
            'governorate':     r['club__governorate'],
            'total_collected': r['total_collected'],
        }
        for r in rows
    }


# ─────────────────────────────────────────────────────────────────────────────
# Path B — sent per club
# ONE query instead of two, values() instead of ORM objects
# ─────────────────────────────────────────────────────────────────────────────

def _sent_per_club(club_name, governorate, date_from=None, date_to=None) -> dict[str, dict]:
    qs = (
        ClubPayout.objects
        .values(
            'club_id',
            'id',
            'amount',
            'date',
            'notes',
            'done_by',
        )
        .order_by('club_id', '-date')
    )

    if club_name:
        qs = qs.filter(club__name__icontains=club_name.strip())
    if governorate is not None:
        qs = qs.filter(club__governorate=governorate)
    if date_from is not None:                          # ← add
        qs = qs.filter(date__gte=date_from)
    if date_to is not None:                            # ← add
        qs = qs.filter(date__lte=date_to)

    totals:  dict[str, Decimal] = {}
    history: dict[str, list]   = {}

    for row in qs:
        cid = str(row['club_id'])
        totals[cid] = totals.get(cid, Decimal('0')) + (row['amount'] or Decimal('0'))
        history.setdefault(cid, []).append({
            'payout_id':  str(row['id']),
            'amount':     row['amount'],
            'date':       row['date'],
            'notes':      row['notes'],
            'done_by': row['done_by'],
        })

    return {
        cid: {
            'total_sent': totals[cid],
            'history':    history[cid],
        }
        for cid in totals
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def get_clubs_payout_summary(
    *,
    club_name:   str | None = None,
    governorate: int | None = None,
    date_from=None,                                    # ← add
    date_to=None,                                      # ← add
) -> list[dict]:

    args = (club_name, governorate)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_collected = pool.submit(_collected_per_club, *args)
        f_sent      = pool.submit(_sent_per_club, club_name, governorate, date_from, date_to)  # ← pass dates
        collected   = f_collected.result()
        sent        = f_sent.result()

    all_ids = set(collected.keys()) | set(sent.keys())
    results = []

    for cid in all_ids:
        c = collected.get(cid, {})
        s = sent.get(cid, {'total_sent': Decimal('0'), 'history': []})

        total_collected = c.get('total_collected', Decimal('0'))
        total_sent      = s['total_sent']
        gov             = c.get('governorate')

        results.append({
            'club_id':         cid,
            'club_name':       c.get('club_name', ''),
            'governorate':     str(SyrianGovernorate(gov).label) if gov is not None else None,
            'total_collected': total_collected,
            'total_sent':      total_sent,
            'balance_owed':    total_collected - total_sent,
            'payout_history':  s['history'],
        })

    return sorted(results, key=lambda x: x['balance_owed'], reverse=True)

# ─────────────────────────────────────────────────────────────────────────────
# record_payout — targeted single-club balance check, not full summary
# ─────────────────────────────────────────────────────────────────────────────


def _get_single_club_balance(club_id: str, date_from=None, date_to=None) -> Decimal:  # ← add dates
    collected = (
        Booking.objects
        .filter(
            club_id=club_id,
            status__in=REVENUE_STATUSES,
            payment_status__in=ONLINE_PAY_STATUSES,
        )
        .annotate(
            row_revenue=Case(
                When(payment_status=PayStatus.DEPOSIT_ONLINE, then='deposit'),
                When(payment_status=PayStatus.ONLINE,         then='final_price'),
                default=Value(Decimal('0')),
                output_field=DecimalField(),
            )
        )
        .aggregate(total=Coalesce(Sum('row_revenue'), Decimal('0')))
    )['total']

    sent_qs = ClubPayout.objects.filter(club_id=club_id)
    if date_from is not None:                          # ← add
        sent_qs = sent_qs.filter(date__gte=date_from)
    if date_to is not None:                            # ← add
        sent_qs = sent_qs.filter(date__lte=date_to)

    sent = sent_qs.aggregate(
        total=Coalesce(Sum('amount'), Decimal('0'))
    )['total']

    return collected - sent

def record_payout(
    club_id:    str,
    amount:     Decimal,
    date,
    notes:      str,
    done_by,
) -> ClubPayout:
    """
    Validates against a single-club balance check — not the full summary.
    Before: O(all clubs). After: O(1 club) — two targeted aggregations.
    """
    balance_owed = _get_single_club_balance(str(club_id))

    if amount > balance_owed:
        raise ValidationError({
            'error': f"المبلغ المُدخَل ({amount}) أكبر من المستحق للنادي ({balance_owed})."
        })

    return ClubPayout.objects.create(
        club_id    = club_id,
        amount     = amount,
        date       = date,
        notes      = notes,
        done_by = done_by,
    )