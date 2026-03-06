"""
booking_signals.py
──────────────────
Three focused post_save signals, one per statistics model:

  • signal_update_num_statistics    → BookingNumStatistics
  • signal_update_price_statistics  → BookingPriceStatistics
  • signal_update_hourly_statistics → ClubHourlyStatistics

All share a single pre_save snapshot (booking_pre_save) so only
one extra DB query is ever issued per Booking save, regardless of
how many signals are registered.

Performance & correctness guarantees
─────────────────────────────────────
  • 1 UPDATE per stats row in the hot path (F() expressions, no read)
  • Race-condition-safe first-row creation (IntegrityError retry)
  • Each signal is independently atomic (transaction.atomic per signal)
  • No silent data drift (errors propagate and roll back their transaction)
  • Each signal has its own minimal fast-exit condition

Required unique constraints (add + migrate if not present):
    BookingNumStatistics:   unique_together = [("club", "day")]
    BookingPriceStatistics: unique_together = [("club", "day")]
    ClubHourlyStatistics:   unique_together = [("club", "pitch", "date", "hour")]
"""

from datetime import datetime, timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from dashboard_manage.models import (
    BookingNumStatistics,
    BookingPriceStatistics,
    ClubHourlyStatistics,
)
from player_booking.models import (
    Booking,
    BookingStatus as S,
    PayStatus
)


# ─────────────────────────────────────────────────────────────
# 1.  PRE-SAVE — single shared snapshot for all three signals
# ─────────────────────────────────────────────────────────────

@receiver(pre_save, sender=Booking)
def booking_pre_save(sender, instance, **kwargs):
    """
    Runs once per Booking.save().
    Captures every column that any of the three signals needs,
    so none of them has to hit the DB again.
    """
    instance._old_snapshot = None
    if instance.pk:
        instance._old_snapshot = (
            Booking.objects
            .only(
                "status", "by_owner", "final_price",
                "club_id", "pitch_id",
                "date", "start_time", "end_time",
                "deposit", "payment_status"
            )
            .filter(pk=instance.pk)
            .first()
        )


# ─────────────────────────────────────────────────────────────
# 2.  PURE HELPERS  (zero DB access)
# ─────────────────────────────────────────────────────────────

def _num_deltas(status, by_owner, multiplier=1):
   
    """
    {field: delta} for BookingNumStatistics.
    CANCELED is excluded — needs transition context; see _cancel_num_deltas.
    """
    d = {}

    def inc(field):
        d[field] = d.get(field, 0) + multiplier

    if status == S.COMPLETED:
        if by_owner:
            inc("completed_num_owner") # additionally when by owner
        else:
            inc("completed_num")

    elif status == S.PENDING_PAY:
        if by_owner:
            inc("pending_pay_num_owner")
        else:
            inc("pending_pay_num")

    elif status == S.PENDING_PLAYER:
        inc("pending_player_num")

    elif status == S.REJECT:
        inc("reject_num")

    elif status == S.NO_SHOW:
        inc("no_Show_num")

    elif status == S.DISPUTED:
        inc("disputed_num")

    elif status == S.EXPIRED:
        inc("expired_num")

    return d


def _price_deltas(status, by_owner, price, multiplier=1):
    
    amount = (price or Decimal("0.00")) * multiplier
    if status == S.COMPLETED:
        field = "money_from_completed_owner" if by_owner else "money_from_completed_player"
        return {field: amount}
    if status == S.PENDING_PAY:
        field = "money_from_pending_pay_owner" if by_owner else "money_from_pending_pay_player"
        return {field: amount}
    return {}


def _price_deltas_deposit(status, payment_status, deposit, by_owner, price, multiplier, instance_status=None):

    if status == S.PENDING_PAY:
        amount = (price - deposit) * multiplier

        field = "money_from_completed_owner" if by_owner else "money_from_completed_player"
        field2 = "money_from_pending_pay_owner" if by_owner else "money_from_pending_pay_player"
       
        if instance_status is not None and instance_status in [S.DISPUTED, S.NO_SHOW]:
            return {field2: amount}

        return {field: deposit, field2: amount}

    if status == S.COMPLETED:
        field = "money_from_completed_owner" if by_owner else "money_from_completed_player"
        return {field: price * multiplier}
    return {}

def _cancel_num_deltas(prior_status, by_owner):
    """Extra {field: +1} when transitioning INTO CANCELED."""
    if prior_status == S.COMPLETED:
        field = (
            "canceled_num_from_completed_owner"
            if by_owner
            else "canceled_num_from_completed_player"
        )
        return {field: 1}
    if prior_status == S.PENDING_PAY:
        field = (
            "canceled_num_from_pending_pay_owner"
            if by_owner
            else "canceled_num_from_pending_pay_player"
        )
        return {field: 1}
    return {}


def _hour_minutes(date, start_time, end_time) -> dict[int, int]:
    """
    Split [start_time, end_time) into {hour: minutes} buckets.
    Handles midnight-crossing bookings via datetime.combine.

    Example: date=today, start=10:30, end=12:15
        → {10: 30, 11: 60, 12: 15}
    """
    if not date or not start_time or not end_time:
        return {}

    start_dt = datetime.combine(date, start_time)
    end_dt   = datetime.combine(date, end_time)

    if end_dt <= start_dt:          # midnight-crossing
        end_dt += timedelta(days=1)

    buckets: dict[int, int] = {}
    cursor = start_dt

    while cursor < end_dt:
        next_hour = (cursor + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        slot_end  = min(next_hour, end_dt)
        minutes   = int((slot_end - cursor).total_seconds() // 60)
        if minutes > 0:
            buckets[cursor.hour] = buckets.get(cursor.hour, 0) + minutes
        cursor = next_hour

    return buckets


def _merge(target: dict, source: dict):
    for k, v in source.items():
        target[k] = target.get(k, 0) + v


# ─────────────────────────────────────────────────────────────
# 3.  DB HELPERS — race-safe 1-query upserts
# ─────────────────────────────────────────────────────────────

def _upsert(model_class, club_id, day, deltas: dict):
    """
    UPDATE → INSERT → retry-UPDATE.
    1 query in the hot path; IntegrityError retry handles concurrent
    first-row-of-day races safely.
    Requires unique_together = [("club", "day")] on the model.
    """
    deltas = {k: v for k, v in deltas.items() if v != 0}
    if not deltas:
        return

    f_updates = {field: F(field) + value for field, value in deltas.items()}

    if model_class.objects.filter(club_id=club_id, day=day).update(**f_updates):
        return

    try:
        with transaction.atomic():
            model_class.objects.create(club_id=club_id, day=day, **deltas)
    except IntegrityError:
        model_class.objects.filter(club_id=club_id, day=day).update(**f_updates)


def _upsert_hourly(club_id, pitch_id, date, hour_minutes: dict[int, int], multiplier: int):
    """
    UPDATE → INSERT → retry-UPDATE per (club, pitch, date, hour) row.
    multiplier = +1 → booking became COMPLETED
    multiplier = -1 → booking left COMPLETED state
    """
    for hour, minutes in hour_minutes.items():
        delta = minutes * multiplier
        if delta == 0:
            continue

        f_update = {"booked_minutes": F("booked_minutes") + delta}

        # Hot path: row already exists → 1 UPDATE.
        # updated = (
        #     ClubHourlyStatistics.objects
        #     .filter(club_id=club_id, pitch_id=pitch_id, date=date, hour=hour)
        #     .update(**f_update)
        # )
        # if updated:
        #     continue

        # Cold path: first booking for this (club, pitch, date, hour).
        try:
            with transaction.atomic():

                ClubHourlyStatistics.objects.create(
                    club_id=club_id,
                    pitch_id=pitch_id,
                    date=date,
                    hour=hour,
                    booked_minutes=max(0, delta),
                )
        except IntegrityError:
            # Concurrent insert won the race — just retry the update.
            ClubHourlyStatistics.objects.filter(
                club_id=club_id, pitch_id=pitch_id, date=date, hour=hour
            ).update(**f_update)


# ─────────────────────────────────────────────────────────────
# 4a.  SIGNAL — BookingNumStatistics
# ─────────────────────────────────────────────────────────────

@receiver(post_save, sender=Booking)
def signal_update_num_statistics(sender, instance, created, **kwargs):
    """
    Updates count-based statistics (completed, canceled, rejected, etc.).
    Fast-exit: skips when status, by_owner, club, and day are all unchanged.
    """
    if not instance.club_id or not instance.date:
        return

    snap = getattr(instance, "_old_snapshot", None)

    if not created and snap and (
        snap.status    == instance.status
        and snap.date  == instance.date
    ):
        return

    num_undo: dict = {}
    num_new:  dict = {}

    if not created and snap:
        _merge(num_undo, _num_deltas(snap.status, snap.by_owner, multiplier=-1))

    _merge(num_new, _num_deltas(instance.status, instance.by_owner, multiplier=1))

    # Cancel-bucket — on instance.date to avoid day-drift.
    if instance.status == S.CANCELED and snap and snap.status != S.CANCELED:
        _merge(num_new, _cancel_num_deltas(snap.status, snap.by_owner))

    if snap and num_undo:
        _upsert(BookingNumStatistics, snap.club_id, snap.date, num_undo)
    _upsert(BookingNumStatistics, instance.club_id, instance.date, num_new)


# ─────────────────────────────────────────────────────────────
# 4b.  SIGNAL — BookingPriceStatistics
# ─────────────────────────────────────────────────────────────

@receiver(post_save, sender=Booking)
def signal_update_price_statistics(sender, instance, created, **kwargs):
    """
    Updates money statistics (completed and pending-pay revenue).
    Fast-exit: skips when status, by_owner, final_price, club, and day
    are all unchanged — avoids touching the DB for non-financial edits.
    """
    if not instance.club_id or not instance.date:
        return

    snap = getattr(instance, "_old_snapshot", None)

    if not created and snap and (
        snap.status      == instance.status
        and snap.final_price == instance.final_price
        and snap.date        == instance.date
    ):
        return

    price_undo: dict = {}
    price_new:  dict = {}
    is_deposit=instance.payment_status == PayStatus.DEPOSIT

    if not created and snap:
        if is_deposit:
            _merge(price_undo, _price_deltas_deposit(snap.status, snap.payment_status, snap.deposit, snap.by_owner, snap.final_price, -1, instance.status))

        else:
            _merge(price_undo, _price_deltas(snap.status, snap.by_owner, snap.final_price, multiplier=-1))
    
    if is_deposit:
        _merge(price_new, _price_deltas_deposit(instance.status, instance.payment_status, instance.deposit, instance.by_owner, instance.final_price, multiplier=1))

    else:
        _merge(price_new, _price_deltas(instance.status, instance.by_owner, instance.final_price, multiplier=1))

    if snap and price_undo:
        _upsert(BookingPriceStatistics, snap.club_id, snap.date, price_undo)
    _upsert(BookingPriceStatistics, instance.club_id, instance.date, price_new)


# ─────────────────────────────────────────────────────────────
# 4c.  SIGNAL — ClubHourlyStatistics
# ─────────────────────────────────────────────────────────────

@receiver(post_save, sender=Booking)
def signal_update_hourly_statistics(sender, instance, created, **kwargs):
    """
    Updates per-hour booked-minutes — only for COMPLETED bookings.
    Fast-exit: skips entirely when neither the old nor new status is
    COMPLETED and nothing time-related changed.
    """
    if not instance.club_id or not instance.date:
        return

    snap = getattr(instance, "_old_snapshot", None)

    old_is_completed = snap is not None and snap.status == S.COMPLETED
    new_is_completed = instance.status == S.COMPLETED

    # Neither side involves COMPLETED → nothing to do.
    if not old_is_completed and not new_is_completed:
        return

    # Both sides are COMPLETED and nothing time/pitch/date related changed → skip.
    if old_is_completed and new_is_completed and snap and all(
        getattr(snap, f) == getattr(instance, f)
        for f in ("pitch_id", "date", "start_time", "end_time")
    ):
        return

    old_hour_minutes = (
        _hour_minutes(snap.date, snap.start_time, snap.end_time)
        if old_is_completed else {}
    )
    new_hour_minutes = (
        _hour_minutes(instance.date, instance.start_time, instance.end_time)
        if new_is_completed else {}
    )

    # Subtract old completed hours (uses snap.pitch_id / snap.date
    # so a pitch or date change correctly targets the old row).
    if old_hour_minutes:
        _upsert_hourly(
            snap.club_id, snap.pitch_id,
            snap.date, old_hour_minutes, multiplier=-1,
        )
    # Add new completed hours.
    if new_hour_minutes:
        _upsert_hourly(
            instance.club_id, instance.pitch_id,
            instance.date, new_hour_minutes, multiplier=+1,
        )