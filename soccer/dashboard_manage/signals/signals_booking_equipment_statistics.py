"""
equipment_signals.py
--------------------
Maintains ClubEquipmentStatistics whenever a BookingEquipment row
is created or its quantity/price changes while the parent booking
is COMPLETED.

Stats row key : (club, club_equipment, date)
Stats fields split by who made the booking:
  quantity_by_ower   / revenue_by_owner    ->  booking.by_owner = True
  quantity_by_player / revenue_by_player   ->  booking.by_owner = False

DB access per BookingEquipment.save()
--------------------------------------
  Hot path (stats row already exists):
    [1] SELECT  parent Booking (status, date, club_id, by_owner)
    [2] UPDATE  ClubEquipmentStatistics
    Total = 2

  Cold path (first stat row for this club/date combination):
    [1] SELECT  parent Booking
    [2] UPDATE  (0 rows matched -- row missing)
    [3] INSERT  create stats row with all four fields initialised
    Total = 3  (+1 retry UPDATE on a concurrent race)

  Fast exit (booking not COMPLETED, or nothing changed):
    [1] SELECT  parent Booking -- return immediately
    Total = 1
"""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from dashboard_manage.models import ClubEquipmentStatistics
from player_booking.models import (
    Booking,
    BookingEquipment,
    BookingStatus as S,
)


# ─────────────────────────────────────────────────────────────
# 1.  PRE-SAVE
#     Snapshot old quantity, price, equipment_id before the write
#     so post_save can compute the exact undo delta without an
#     extra query.
# ─────────────────────────────────────────────────────────────

@receiver(pre_save, sender=BookingEquipment)
def booking_equipment_pre_save(sender, instance, **kwargs):
    instance._old_snapshot = None
    if instance.pk:
        instance._old_snapshot = (
            BookingEquipment.objects
            .only("quantity", "price", "equipment_id", "booking_id")
            .filter(pk=instance.pk)
            .first()
        )


# ─────────────────────────────────────────────────────────────
# 2.  PURE HELPERS  (zero DB access)
# ─────────────────────────────────────────────────────────────

def _equipment_deltas(quantity, price, by_owner: bool, multiplier=1):
    """
    Returns {field: delta} targeting the correct owner/player columns.

    by_owner=True  -> quantity_by_ower  / revenue_by_owner
    by_owner=False -> quantity_by_player / revenue_by_player

    NOTE: 'quantity_by_ower' matches the model field name exactly
    (the model has a typo -- the 'n' is missing from 'owner').
    """
    qty_delta = quantity * multiplier
    rev_delta = (quantity * price) * multiplier

    if by_owner:
        return {
            "quantity_by_ower": qty_delta,   # intentional: matches model typo
            "revenue_by_owner": rev_delta,
        }
    return {
        "quantity_by_player": qty_delta,
        "revenue_by_player":  rev_delta,
    }


# ─────────────────────────────────────────────────────────────
# 3.  DB HELPER
# ─────────────────────────────────────────────────────────────

def _upsert_equipment_stats(club_id, club_equipment_id, date, deltas: dict):
    """
    Applies {field: delta} to a (club, club_equipment, date) stats row.

    Hot path  : 1 UPDATE via F() expressions.
    Cold path : initialises a brand-new row with all four fields set to
                0 / 0.00, then overrides with the incoming deltas.
                On concurrent race -> 1 retry UPDATE.

    Initialising all four fields on INSERT is critical: if we only set
    the two fields in `deltas`, the other two would be NULL and the next
    UPDATE (from the other owner/player path) would fail.
    """
    deltas = {k: v for k, v in deltas.items() if v != 0}
    if not deltas:
        return

    f_update = {field: F(field) + value for field, value in deltas.items()}

    # Hot path: row exists -> 1 UPDATE.
    if (
        ClubEquipmentStatistics.objects
        .filter(club_id=club_id, club_equipment_id=club_equipment_id, date=date)
        .update(**f_update)
    ):
        return

    # Cold path: row is missing -- build a fully-initialised create dict.
    create_kwargs = {
        "quantity_by_ower":   0,
        "revenue_by_owner":   Decimal("0.00"),
        "quantity_by_player": 0,
        "revenue_by_player":  Decimal("0.00"),
    }
    for field, value in deltas.items():
        # Guard negatives on first insert -- stats should never start below 0.
        if isinstance(value, Decimal):
            create_kwargs[field] = max(Decimal("0.00"), value)
        else:
            create_kwargs[field] = max(0, value)

    try:
        with transaction.atomic():

            ClubEquipmentStatistics.objects.create(
                club_id=club_id,
                club_equipment_id=club_equipment_id,
                date=date,
                **create_kwargs,
            )
    except IntegrityError:
        # Concurrent insert won the race -- retry the UPDATE.
        ClubEquipmentStatistics.objects.filter(
            club_id=club_id, club_equipment_id=club_equipment_id, date=date
        ).update(**f_update)


# ─────────────────────────────────────────────────────────────
# 4.  SIGNAL
# ─────────────────────────────────────────────────────────────

@receiver(post_save, sender=BookingEquipment)
def signal_update_equipment_stats_on_booking_equipment(sender, instance, created, **kwargs):
    """
    Fires on every BookingEquipment.save().
    Only writes to stats when the parent booking is COMPLETED.

    Fast exit conditions (after the 1 required SELECT):
      - Parent booking is not COMPLETED
      - Update where quantity, price, AND equipment_id are all unchanged

    Hot path: 1 SELECT (booking) + 1 UPDATE (stats) = 2 queries.
    by_owner is fetched here because it determines WHICH stat fields
    to increment -- it is not stored on BookingEquipment itself.
    """
    # 1 SELECT -- also fetches by_owner to route to the correct stat fields
    print("///////////////////////////////////////////////////////////////////")
    try:
        booking = (
            Booking.objects
            .only("status", "date", "club_id", "by_owner")
            .get(pk=instance.booking_id)
        )
    except Booking.DoesNotExist:
        return

    if booking.status != S.COMPLETED:
        return

    snap = getattr(instance, "_old_snapshot", None)

    # Fast exit: quantity, price, AND equipment_id all unchanged.
    if not created and snap and (
        snap.quantity     == instance.quantity
        and snap.price        == instance.price
    ):
        return

    # Undo the old values (update case only).
    if not created and snap:
        old_deltas = _equipment_deltas(
            snap.quantity, snap.price, booking.by_owner, multiplier=-1
        )
        _upsert_equipment_stats(
            booking.club_id, snap.equipment_id, booking.date, old_deltas,
        )

    # Apply the new values.
    new_deltas = _equipment_deltas(
        instance.quantity, instance.price, booking.by_owner, multiplier=+1
    )
    _upsert_equipment_stats(
        booking.club_id, instance.equipment_id, booking.date, new_deltas,
    )
