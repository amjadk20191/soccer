from django.db import connection
from django.db.models import Q, FloatField, ExpressionWrapper, F
from django.db.models.functions import ACos, Cos, Sin, Radians
from dashboard_manage.models import Club

from player_booking.models import Booking
from dashboard_manage.models import ClubPricing
from ..models import Pitch
from soccer.enm import BOOKING_STATUS_DENIED


class PitchSearchService:
    """
    Searches available pitches for a given date/time slot.

    Priority system (mirrors ClubTimeForOwnerService):
      1. Date-specific ClubPricing  (type=2)  — highest priority
      2. Weekday ClubPricing        (type=1)  — medium priority
      3. Club.open_time / close_time           — fallback

    Custom weekday formula (matches ClubTimeForOwnerService):
      weekday_idx = (date.weekday() + 2) % 7

    working_days is a JSON dict with string keys: {"0": true, "2": false, ...}

    Distance is calculated inside the DB (Haversine via trig functions),
    which allows true queryset-level ordering and DB pagination.
    """

    # ── Public API ──────────────────────────────────────────────────────────

    @classmethod
    def search(
        cls,
        date,
        start_time,
        end_time,
        user_lat: float,
        user_lon: float,
        pitch_type=None,
        size_high=None,
        size_width=None,
    ) -> tuple:
        weekday_idx = cls._custom_weekday(date)

        booked_pitch_ids        = cls._get_booked_pitch_ids(date, start_time, end_time)
        date_exception_club_ids = cls._get_date_exception_club_ids(date)

        qs = cls._get_candidate_pitches(
            weekday_idx,
            booked_pitch_ids,
            date_exception_club_ids,
            pitch_type,
            size_high,
            size_width,
        )

        qs, effective_hours_map = cls._apply_effective_hours_filter(  # ← unpack here
            qs, date, weekday_idx, start_time, end_time
        )

        qs = cls._annotate_distance(qs, user_lat, user_lon)  # ← now receives queryset, not tuple

        return qs.order_by('distance_km'), effective_hours_map
        # ── Private: weekday ────────────────────────────────────────────────────

    @staticmethod
    def _custom_weekday(date) -> int:
        """Mon(0)→2, Tue(1)→3, Wed(2)→4, Thu(3)→5, Fri(4)→6, Sat(5)→0, Sun(6)→1"""
        return (date.weekday() + 2) % 7

    # ── Private: booking exclusion ──────────────────────────────────────────

    @staticmethod
    def _get_booked_pitch_ids(date, start_time, end_time):
        return (
            Booking.objects
            .filter(
                date=date,
                status__in=BOOKING_STATUS_DENIED,
                start_time__lt=end_time,
                end_time__gt=start_time,
            )
            .values_list('pitch_id', flat=True)
        )

    # ── Private: open-day filtering ─────────────────────────────────────────

    @staticmethod
    def _get_date_exception_club_ids(date):
        """Clubs explicitly scheduled open on this date — overrides working_days."""
        return (
            ClubPricing.objects
            .filter(type=2, date=date)
            .values_list('club_id', flat=True)
            .distinct()
        )


    @classmethod
    def _get_open_club_ids(cls, weekday_idx: int, date_exception_club_ids) -> list:
        """
        Resolve which clubs are open on this weekday in Python.
        Works on both SQLite (dev) and PostgreSQL (prod) — no JSON DB operators needed.
        """
        all_clubs = (
            Club.objects
            .filter(is_active=True)
            .values('id', 'working_days')
        )

        open_via_working_days = [
            club['id']
            for club in all_clubs
            if club['working_days'].get(str(weekday_idx)) is True
        ]

        # Merge both sources — date exceptions + working_days
        return list(set(open_via_working_days) | set(date_exception_club_ids))


    @classmethod
    def _get_candidate_pitches(
        cls,
        weekday_idx,
        booked_pitch_ids,
        date_exception_club_ids,
        pitch_type,
        size_high,
        size_width,
    ):
        open_club_ids = cls._get_open_club_ids(weekday_idx, date_exception_club_ids)

        qs = (
            Pitch.objects
            .filter(
                is_active=True,
                is_deteted=False,
                club__is_active=True,
                club_id__in=open_club_ids,   # ← simple IN lookup, works everywhere
            )
            .exclude(id__in=booked_pitch_ids)
            .select_related('club')
        )

        if pitch_type is not None:
            qs = qs.filter(type=pitch_type)
        if size_high is not None:
            qs = qs.filter(size_high=size_high)
        if size_width is not None:
            qs = qs.filter(size_width=size_width)

        return qs
    # ── Private: effective hours (bulk fetch → Python resolution) ───────────

    @classmethod
    def _apply_effective_hours_filter(cls, qs, date, weekday_idx, start_time, end_time):
        club_ids = list(qs.values_list('club_id', flat=True).distinct())

        if not club_ids:
            return qs.none(), {'date': {}, 'weekday': {}}

        exceptions = (
            ClubPricing.objects
            .filter(club_id__in=club_ids)
            .filter(
                Q(type=2, date=date) |
                Q(type=1, day_of_week=weekday_idx)
            )
            .values('club_id', 'start_time', 'end_time', 'type')
            .order_by('club_id', '-type')
        )

        date_rules    = {}
        weekday_rules = {}
        for row in exceptions:
            cid = row['club_id']
            if row['type'] == 2:
                date_rules[cid] = row
            elif row['type'] == 1 and cid not in date_rules:
                weekday_rules[cid] = row

        effective_hours_map = {'date': date_rules, 'weekday': weekday_rules}

        from dashboard_manage.models import Club
        default_map = {
            c['id']: c
            for c in Club.objects.filter(id__in=club_ids).values('id', 'open_time', 'close_time')
        }

        open_club_ids = []
        for cid in club_ids:
            if cid in date_rules:
                o, c = date_rules[cid]['start_time'], date_rules[cid]['end_time']
            elif cid in weekday_rules:
                o, c = weekday_rules[cid]['start_time'], weekday_rules[cid]['end_time']
            else:
                defaults = default_map.get(cid)
                if not defaults:
                    continue
                o, c = defaults['open_time'], defaults['close_time']

            if o <= start_time and c >= end_time:
                open_club_ids.append(cid)

        return qs.filter(club_id__in=open_club_ids), effective_hours_map  # ← return map


    # ── Private: DB-level distance annotation ───────────────────────────────

    @staticmethod
    def _annotate_distance(qs, user_lat: float, user_lon: float):
        """
        Annotate each pitch with distance_km using the Haversine formula
        expressed in DB trig functions (no PostGIS required).

        Formula: 6371 * ACos(
            Sin(rad(user_lat)) * Sin(rad(club_lat)) +
            Cos(rad(user_lat)) * Cos(rad(club_lat)) * Cos(rad(club_lon) - rad(user_lon))
        )
        """
        return qs.annotate(
            distance_km=ExpressionWrapper(
                6371.0 * ACos(
                    Sin(Radians(user_lat)) * Sin(Radians(F('club__latitude'))) +
                    Cos(Radians(user_lat)) * Cos(Radians(F('club__latitude'))) *
                    Cos(Radians(F('club__longitude')) - Radians(user_lon))
                ),
                output_field=FloatField(),
            )
        )
    


    
    @staticmethod
    def _resolve_club_hours(club, effective_hours_map) -> tuple:
        cid = club.id
        if cid in effective_hours_map['date']:
            row = effective_hours_map['date'][cid]
            return row['start_time'], row['end_time']
        if cid in effective_hours_map['weekday']:
            row = effective_hours_map['weekday'][cid]
            return row['start_time'], row['end_time']
        return club.open_time, club.close_time