"""
equipment_signals.py
--------------------
Maintains ClubEquipmentStatistics when a Booking crosses the COMPLETED
status boundary in either direction.

  Booking -> COMPLETED        : add all BookingEquipment rows to stats
  COMPLETED -> anything else  : subtract all BookingEquipment rows from stats

Stats row key : (club, club_equipment, date)
Stats fields split by who made the booking:
  quantity_by_ower   / revenue_by_owner    ->  booking.by_owner = True
  quantity_by_player / revenue_by_player   ->  booking.by_owner = False

Connection to booking_signals.py
----------------------------------
  booking_pre_save (booking_signals.py) sets instance._old_snapshot once
  per Booking.save(). This file reads that attribute for free -- no extra
  Booking SELECT is needed here.

  Load order in apps.py:
    import booking_signals    # sets _old_snapshot
    import equipment_signals  # reads _old_snapshot

DB access per Booking.save()
------------------------------
  COMPLETED boundary crossed (M = BookingEquipment rows):

    Hot path (all ClubEquipmentStatistics rows already exist):
      [1] SELECT  BookingEquipment rows         -- unavoidable
      [2] UPDATE  ClubEquipmentStatistics       -- 1 bulk CASE/WHEN for all M
      Total = 2  regardless of M

    Cold path (some stats rows missing -- first booking of the day):
      [1] SELECT  BookingEquipment rows
      [2] UPDATE  bulk CASE/WHEN (hits existing rows only)
      [3] SELECT  find which equipment_ids have no stats row
      [4] INSERT  bulk_create for ALL missing items (1 statement)
           On IntegrityError race -> fall back to per-row upserts
      Total = 4  (was 2 + M_missing without bulk_create)

  COMPLETED boundary NOT crossed:
    Total = 0  -- fast exit, zero queries
"""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Case, DecimalField, F, IntegerField, Value, When
from django.db.models.signals import post_save
from django.dispatch import receiver

from dashboard_manage.models import ClubEquipmentStatistics
from player_booking.models import (
    Booking,
    BookingEquipment,
    BookingStatus as S,
)


# ─────────────────────────────────────────────────────────────
# 1.  PURE HELPERS  (zero DB access)
# ─────────────────────────────────────────────────────────────

def _build_deltas(items: list, by_owner: bool, multiplier: int) -> dict:
    """
    Builds {club_equipment_id: (qty_delta, rev_delta)} for all items.

    by_owner=True  -> quantity_by_ower  / revenue_by_owner
    by_owner=False -> quantity_by_player / revenue_by_player

    NOTE: quantity_by_ower matches the model field name exactly
    (the model has a typo -- the n is missing from owner).
    """
    deltas = {}
    for be in items:
        qty_d = be.quantity * multiplier
        rev_d = (be.quantity * be.price) * multiplier
        deltas[be.equipment_id] = (qty_d, rev_d)
    return deltas


def _qty_field(by_owner: bool) -> str:
    return "quantity_by_ower" if by_owner else "quantity_by_player"


def _rev_field(by_owner: bool) -> str:
    return "revenue_by_owner" if by_owner else "revenue_by_player"


# ─────────────────────────────────────────────────────────────
# 2.  DB HELPER
# ─────────────────────────────────────────────────────────────

def _bulk_apply_equipment(club_id, date, items: list, by_owner: bool, multiplier: int):
    """
    Updates ALL M equipment items in the fewest possible queries.

    Hot path  : 1 bulk CASE/WHEN UPDATE for all M items.
    Cold path : 1 UPDATE + 1 SELECT + 1 bulk_create for missing rows.
                Falls back to per-row upserts on a concurrent race.

    WHY NOT ignore_conflicts=True on bulk_create:
      It silently drops conflicting rows, losing the delta permanently.
      We use bulk_create WITHOUT ignore_conflicts and catch IntegrityError
      so the whole batch rolls back before falling back to per-row upserts.
    """
    if not items:
        return

    deltas = _build_deltas(items, by_owner, multiplier)
    equipment_ids = list(deltas.keys())

    qty_f = _qty_field(by_owner)
    rev_f = _rev_field(by_owner)

    qty_cases = [When(club_equipment_id=eid, then=Value(d[0])) for eid, d in deltas.items()]
    rev_cases = [When(club_equipment_id=eid, then=Value(d[1])) for eid, d in deltas.items()]

    # ── Hot path: 1 bulk CASE/WHEN UPDATE ────────────────────
    updated_count = (
        ClubEquipmentStatistics.objects
        .filter(club_id=club_id, date=date, club_equipment_id__in=equipment_ids)
        .update(
            **{
                qty_f: F(qty_f) + Case(
                    *qty_cases, default=Value(0),
                    output_field=IntegerField(),
                ),
                rev_f: F(rev_f) + Case(
                    *rev_cases, default=Value(Decimal("0")),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
            }
        )
    )

    if updated_count == len(deltas):
        return  # All rows existed -- done in 1 query.

    # ── Cold path: find missing rows ─────────────────────────
    existing_ids = set(
        ClubEquipmentStatistics.objects
        .filter(club_id=club_id, date=date, club_equipment_id__in=equipment_ids)
        .values_list("club_equipment_id", flat=True)
    )
    missing = [eid for eid in equipment_ids if eid not in existing_ids]
    if not missing:
        return

    # ── Bulk INSERT for all missing items (1 statement) ───────
    def _make_row(eid):
        qty_d, rev_d = deltas[eid]
        return ClubEquipmentStatistics(
            club_id=club_id,
            club_equipment_id=eid,
            date=date,
            quantity_by_ower=max(0, qty_d)            if by_owner else 0,
            revenue_by_owner=max(Decimal("0.00"), rev_d) if by_owner else Decimal("0.00"),
            quantity_by_player=0                      if by_owner else max(0, qty_d),
            revenue_by_player=Decimal("0.00")         if by_owner else max(Decimal("0.00"), rev_d),
        )

    try:
        with transaction.atomic():
            ClubEquipmentStatistics.objects.bulk_create([_make_row(eid) for eid in missing])
    except IntegrityError:
        # Concurrent insert raced between SELECT and bulk_create.
        # Whole batch rolled back -- fall back to safe per-row upserts.
        for eid in missing:
            qty_d, rev_d = deltas[eid]
            try:
                with transaction.atomic():

                    ClubEquipmentStatistics.objects.create(
                        club_id=club_id, club_equipment_id=eid, date=date,
                        quantity_by_ower=max(0, qty_d)               if by_owner else 0,
                        revenue_by_owner=max(Decimal("0.00"), rev_d) if by_owner else Decimal("0.00"),
                        quantity_by_player=0                         if by_owner else max(0, qty_d),
                        revenue_by_player=Decimal("0.00")            if by_owner else max(Decimal("0.00"), rev_d),
                    )
            except IntegrityError:
                ClubEquipmentStatistics.objects.filter(
                    club_id=club_id, club_equipment_id=eid, date=date
                ).update(
                    **{
                        qty_f: F(qty_f) + qty_d,
                        rev_f: F(rev_f) + rev_d,
                    }
                )


# ─────────────────────────────────────────────────────────────
# 3.  SIGNAL — Booking status crosses COMPLETED boundary
# ─────────────────────────────────────────────────────────────

@receiver(post_save, sender=Booking)
def signal_update_equipment_stats_on_booking(sender, instance, created, **kwargs):
    """
    Fires on every Booking.save().
    Fast-exits with 0 queries when the COMPLETED boundary is not crossed.

    Uses _old_snapshot set by booking_pre_save in booking_signals.py --
    zero extra Booking SELECTs needed here.

    Hot path: 1 SELECT (BookingEquipment) + 1 bulk UPDATE = 2 queries.
    """
    if not instance.club_id or not instance.date:
        return
    signals_force = getattr(instance, '_force_signals_update', False)

    # Free attribute read -- set by booking_signals.booking_pre_save.
    snap        = getattr(instance, "_old_snapshot", None)
    old_status  = snap.status  if snap else None
    old_date    = snap.date    if snap else None
    old_club_id = snap.club_id if snap else None

    was_completed = old_status      == S.COMPLETED
    now_completed = instance.status == S.COMPLETED

    # Fast exit: COMPLETED boundary not crossed -- 0 queries.
    if (was_completed == now_completed) and not signals_force:
        return

    # 1 SELECT -- unavoidable: need to know what equipment exists.
    items = list(
        BookingEquipment.objects
        .filter(booking_id=instance.pk)
        .only("equipment_id", "quantity", "price")
    )
    if not items:
        return

    if was_completed and not now_completed:
        # Left COMPLETED -> subtract. Use old date/club if they changed.
        _bulk_apply_equipment(
            club_id    = old_club_id or instance.club_id,
            date       = old_date    or instance.date,
            items      = items,
            by_owner   = instance.by_owner,
            multiplier = -1,
        )
    else:
        # Entered COMPLETED -> add.
        _bulk_apply_equipment(
            club_id    = instance.club_id,
            date       = instance.date,
            items      = items,
            by_owner   = instance.by_owner,
            multiplier = +1,
        )
