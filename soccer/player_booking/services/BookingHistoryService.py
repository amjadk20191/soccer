"""
services/booking_service.py

Fetches a paginated, unified timeline of bookings and pending challenges for a player.

─────────────────────────────────────────────────────────────────────────────
MEMBERSHIP RULES (which records belong to a user)
─────────────────────────────────────────────────────────────────────────────

BOOKING (entry_type = 'booking'):
  Case 1 — Direct / non-challenge booking
            booking.player_id = user

  Case 2 — Challenge booking (club has accepted → roster moved to CPB)
            EXISTS ChallengePlayerBooking WHERE booking_id = b.id AND player_id = user

  Case 3 — Challenge booking still PENDING_MANAGER (club hasn't accepted yet)
            The roster still lives in TeamMember, NOT yet in CPB.
            EXISTS Challenge c JOIN TeamMember tm
                ON tm.team_id IN (c.team_id, c.challenged_team_id)
            WHERE c.booking_id = b.id AND tm.player_id = user AND tm.status = ACTIVE

PENDING CHALLENGE (entry_type = 'pending_challenge'):
  Only when status = PENDING_TEAM and booking_id IS NULL.
  (Challenge converts to a booking-challenge when the challenged team accepts.)
  Roster lives in TeamMember for both sides.

─────────────────────────────────────────────────────────────────────────────
ARCHITECTURE (3-step pipeline)
─────────────────────────────────────────────────────────────────────────────
  Step 1 — Raw SQL ID query   (no JOINs on detail tables, no window functions)
  Step 2 — Raw SQL COUNT      (same WHERE, no ORDER BY / LIMIT)
  Step 3 — ORM hydration      (IN-list fetch with select_related / prefetch_related)

  Steps 1 and 2 share one parameter-builder (_build_params) so they can
  never drift out of sync.
─────────────────────────────────────────────────────────────────────────────

RECOMMENDED INDEXES (PostgreSQL)
─────────────────────────────────────────────────────────────────────────────
  CREATE INDEX CONCURRENTLY idx_booking_player_status
      ON bookings (player_id, status, created_at DESC);

  CREATE INDEX CONCURRENTLY idx_booking_challenge_pending
      ON bookings (is_challenge, status, created_at DESC)
      WHERE is_challenge = TRUE;

  CREATE INDEX CONCURRENTLY idx_cpb_player_booking
      ON challenge_player_booking (player_id, booking_id);

  CREATE INDEX CONCURRENTLY idx_tm_player_active
      ON team_member (player_id, status, team_id);

  CREATE INDEX CONCURRENTLY idx_challenge_pending_null
      ON challenges (status, created_at DESC)
      WHERE booking_id IS NULL;
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from django.db import connection

from player_booking.models import Booking, BookingStatus
from player_competition.models import Challenge, ChallengePlayerBooking, ChallengeStatus
from player_team.models import Team, TeamMember, MemberStatus

# ── Table names resolved once at import time ───────────────────────────────────
_TB   = Booking._meta.db_table                # bookings
_TC   = Challenge._meta.db_table              # challenges
_TCPB = ChallengePlayerBooking._meta.db_table # challenge_player_booking
_TM   = TeamMember._meta.db_table             # team_member

# ──────────────────────────────────────────────────────────────────────────────
# Status maps
# ──────────────────────────────────────────────────────────────────────────────
# StatusFilter = (booking_statuses | None, challenge_statuses)
#   None  on booking side  → no status filter (return all booking statuses)
#   []    on either side   → skip that branch entirely
StatusFilter = tuple[list[int] | None, list[int]]

ARABIC_STATUS_MAP: dict[str, StatusFilter] = {
    'بانتظار_تأكيد_النادي':   ([BookingStatus.PENDING_MANAGER], []),
    'وقت_مقترح_جديد':         ([BookingStatus.PENDING_PLAYER],  []),
    'مشكلة_في_النتيجة':       ([],                              [ChallengeStatus.DISPUTED_SCORE]),
    'بانتظار_الفريق_المنافس': ([],                              [ChallengeStatus.PENDING_TEAM]),
    'بانتظار_تكملة_الدفع':    ([BookingStatus.PENDING_PAY],     [ChallengeStatus.PENDING_PAY]),
    'مكتمل':                   ([BookingStatus.COMPLETED],       [ChallengeStatus.ACCEPTED]),
    'ملغى':                    ([BookingStatus.CANCELED],        [ChallengeStatus.CANCELED]),
    'متغيب':                   ([BookingStatus.NO_SHOW],         [ChallengeStatus.NO_SHOW]),
    'مشكلة':                   ([BookingStatus.DISPUTED],        [ChallengeStatus.DISPUTED]),
    'انتهت_صلاحيته':           ([BookingStatus.EXPIRED],         [ChallengeStatus.EXPIRED]),
    'بانتظار_الدفع':           ([BookingStatus.PAY],             [ChallengeStatus.PAY]),
    'بانتظار_تأكبد_الدفع':    ([BookingStatus.CHECK_PAY],       [ChallengeStatus.CHECK_PAY]),
    'مرفوض':                   ([BookingStatus.REJECT],          [ChallengeStatus.REJECTED]),
}

# Reverse maps: status int → Arabic label  (built once at import)
_BOOKING_STATUS_TO_ARABIC:   dict[int, str] = {}
_CHALLENGE_STATUS_TO_ARABIC: dict[int, str] = {}

for _label, (_b, _c) in ARABIC_STATUS_MAP.items():
    for _s in (_b or []):
        _BOOKING_STATUS_TO_ARABIC[_s] = _label
    for _s in _c:
        _CHALLENGE_STATUS_TO_ARABIC[_s] = _label

VALID_ARABIC_STATUSES: list[str] = list(ARABIC_STATUS_MAP.keys())

# Challenges that have no booking yet only ever exist in PENDING_TEAM.
# Once the challenged team accepts → a booking is created → entry_type flips to 'booking'.
_UNLINKED_CHALLENGE_STATUSES: list[int] = [ChallengeStatus.PENDING_TEAM]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _ph(n: int) -> str:
    """Return n comma-separated %s placeholders."""
    return ', '.join(['%s'] * n)


def _to_uuid_str(val: Any) -> str:
    """
    Normalize a raw DB value to a consistent UUID string (with dashes).
    On SQLite, UUIDs come back as 32-char hex strings without dashes.
    On PostgreSQL, they come back as the proper string or uuid object.
    """
    if isinstance(val, uuid.UUID):
        return str(val)
    s = str(val)
    if len(s) == 32 and '-' not in s:          # SQLite hex blob
        return str(uuid.UUID(s))
    return s                                    # already canonical


# ──────────────────────────────────────────────────────────────────────────────
# SQL branch builders
# ──────────────────────────────────────────────────────────────────────────────

def _booking_branch(filter_booking_statuses: list[int] | None) -> str:
    """
    SELECT branch for all booking types:
      - direct bookings       (player_id = user)
      - challenge bookings    (player in ChallengePlayerBooking, post-acceptance)
      - pending-manager       (player in TeamMember, pre-acceptance)
    """
    status_clause = (
        f'AND b.status IN ({_ph(len(filter_booking_statuses))})'
        if filter_booking_statuses else ''
    )
    return f"""
        SELECT b.id AS id, 'booking' AS entry_type, b.created_at
        FROM {_TB} b
        WHERE (
            -- Case 1: direct (non-challenge) booking
            b.player_id = %s

            -- Case 2: confirmed challenge booking — roster is in ChallengePlayerBooking
            OR EXISTS (
                SELECT 1
                FROM   {_TCPB} cpb
                WHERE  cpb.booking_id = b.id
                  AND  cpb.player_id  = %s
            )

            -- Case 3: challenge booking awaiting club approval —
            --         roster is still in TeamMember, NOT yet in ChallengePlayerBooking
            OR (
                b.status       = {BookingStatus.PENDING_MANAGER}
                AND b.is_challenge = TRUE
                AND EXISTS (
                    SELECT 1
                    FROM   {_TC} c2
                    JOIN   {_TM} tm
                           ON tm.team_id IN (c2.team_id, c2.challenged_team_id)
                    WHERE  c2.booking_id = b.id
                      AND  tm.player_id  = %s
                      AND  tm.status     = %s
                )
            )
        )
        {status_clause}
    """

# Params consumed by _booking_branch (in order):
#   %s user_id        (case 1)
#   %s user_id        (case 2)
#   %s user_id        (case 3)
#   %s MemberStatus.ACTIVE (case 3)
#   [booking_statuses if present]


def _challenge_branch(challenge_statuses: list[int]) -> str:
    """
    SELECT branch for pure pending challenges (no booking linked yet).
    Roster for both sides lives in TeamMember.
    """
    return f"""
        SELECT c.id AS id, 'pending_challenge' AS entry_type, c.created_at
        FROM {_TC} c
        WHERE c.status     IN ({_ph(len(challenge_statuses))})
          AND c.booking_id IS NULL
          AND (
              EXISTS (
                  SELECT 1 FROM {_TM} tm
                  WHERE  tm.team_id   = c.team_id
                    AND  tm.player_id = %s
                    AND  tm.status    = %s
              )
              OR EXISTS (
                  SELECT 1 FROM {_TM} tm
                  WHERE  tm.team_id   = c.challenged_team_id
                    AND  tm.player_id = %s
                    AND  tm.status    = %s
              )
          )
    """

# Params consumed by _challenge_branch (in order):
#   [challenge_statuses]
#   %s user_id         (team side)
#   %s MemberStatus.ACTIVE
#   %s user_id         (challenged_team side)
#   %s MemberStatus.ACTIVE


def _combined_branches(
    filter_booking_statuses: list[int] | None,
    challenge_statuses: list[int],
) -> str:
    """Return a UNION ALL of whichever branches are active."""
    include_bookings   = filter_booking_statuses is None or bool(filter_booking_statuses)
    include_challenges = bool(challenge_statuses)

    parts: list[str] = []
    if include_bookings:
        parts.append(_booking_branch(filter_booking_statuses))
    if include_challenges:
        parts.append(_challenge_branch(challenge_statuses))

    return ' UNION ALL '.join(parts)


def _build_id_sql(
    filter_booking_statuses: list[int] | None,
    challenge_statuses: list[int],
) -> str:
    branches = _combined_branches(filter_booking_statuses, challenge_statuses)
    return f"""
        SELECT id, entry_type, created_at
        FROM   ({branches}) combined
        ORDER  BY created_at DESC
        LIMIT  %s OFFSET %s
    """


def _build_count_sql(
    filter_booking_statuses: list[int] | None,
    challenge_statuses: list[int],
) -> str:
    branches = _combined_branches(filter_booking_statuses, challenge_statuses)
    return f'SELECT COUNT(*) FROM ({branches}) t'


def _build_params(
    user_id: str,
    booking_statuses: list[int] | None,
    challenge_statuses: list[int],
    extra: list[Any] | None = None,
) -> list[Any]:
    """
    Build the ordered parameter list that matches _build_id_sql / _build_count_sql.
    `extra` appended at the end — pass [limit, offset] for the ID query.
    """
    include_bookings   = booking_statuses is None or bool(booking_statuses)
    include_challenges = bool(challenge_statuses)

    params: list[Any] = []

    if include_bookings:
        # Booking branch: user_id × 3, MemberStatus.ACTIVE, then optional status list
        params.extend([user_id, user_id, user_id, MemberStatus.ACTIVE])
        if booking_statuses:
            params.extend(booking_statuses)

    if include_challenges:
        # Challenge branch: status list, then two (user_id, ACTIVE) pairs
        params.extend(challenge_statuses)
        params.extend([user_id, MemberStatus.ACTIVE, user_id, MemberStatus.ACTIVE])

    if extra:
        params.extend(extra)

    return params


# ──────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class UserBookingItem:
    entry_type:             str                 # 'booking' | 'pending_challenge'
    id:                     uuid.UUID
    date:                   Any
    start_time:             Any
    end_time:               Any
    final_price:            Any                 # None for pending challenges
    status:                 int | None
    created_at:             Any
    pitch_id:               Any
    pitch_name:             str | None
    club_id:                Any
    club_name:              str | None
    challenge_id:           uuid.UUID | None
    challenge_status:       int | None
    result_team:            int | None
    result_challenged_team: int | None
    team_id:                uuid.UUID | None
    team_name:              str | None
    team_logo:              str | None
    challenged_team_id:     uuid.UUID | None
    challenged_team_name:   str | None
    challenged_team_logo:   str | None
    total_count:            int = field(default=0, compare=False)

    def get_status_display(self) -> str | None:
        if self.entry_type == 'booking' and self.status is not None:
            return _BOOKING_STATUS_TO_ARABIC.get(self.status)
        if self.entry_type == 'pending_challenge' and self.status is not None:
            return _CHALLENGE_STATUS_TO_ARABIC.get(self.status)
        return None


# ──────────────────────────────────────────────────────────────────────────────
# ORM hydration helpers
# ──────────────────────────────────────────────────────────────────────────────

def _hydrate_bookings(booking_ids: list[str]) -> dict[str, UserBookingItem]:
    """
    Fetch full booking rows via ORM using INNER-JOIN-style select_related.
    Returns a dict keyed by canonical UUID string (with dashes).

    IMPORTANT: use list(b.challenge_set.all()) — NOT .first() — to honour
    the prefetch cache. Calling .first() issues a new DB query per booking,
    completely defeating prefetch_related.
    """
    if not booking_ids:
        return {}

    bookings = (
        Booking.objects
        .filter(id__in=booking_ids)
        .select_related('pitch', 'club')
        .prefetch_related(
            'challenge_set__team__logo',
            'challenge_set__challenged_team__logo',
        )
    )

    result: dict[str, UserBookingItem] = {}
    for b in bookings:
        # Read from prefetch cache — zero extra queries
        challenges = list(b.challenge_set.all())
        ch = challenges[0] if challenges else None

        result[str(b.id)] = UserBookingItem(
            entry_type             = 'booking',
            id                     = b.id,
            date                   = b.date,
            start_time             = b.start_time,
            end_time               = b.end_time,
            final_price            = b.final_price,
            status                 = b.status,
            created_at             = b.created_at,
            pitch_id               = b.pitch_id,
            pitch_name             = b.pitch.name if b.pitch else None,
            club_id                = b.club_id,
            club_name              = b.club.name if b.club else None,
            challenge_id           = ch.id if ch else None,
            challenge_status       = ch.status if ch else None,
            result_team            = ch.result_team if ch else None,
            result_challenged_team = ch.result_challenged_team if ch else None,
            team_id                = ch.team_id if ch else None,
            team_name              = ch.team.name if ch and ch.team else None,
            team_logo              = (
                ch.team.logo.logo
                if ch and ch.team and ch.team.logo else None
            ),
            challenged_team_id     = ch.challenged_team_id if ch else None,
            challenged_team_name   = (
                ch.challenged_team.name
                if ch and ch.challenged_team else None
            ),
            challenged_team_logo   = (
                ch.challenged_team.logo.logo
                if ch and ch.challenged_team and ch.challenged_team.logo else None
            ),
        )

    return result


def _hydrate_challenges(challenge_ids: list[str]) -> dict[str, UserBookingItem]:
    """
    Fetch full challenge rows via ORM.
    Returns a dict keyed by canonical UUID string (with dashes).
    """
    if not challenge_ids:
        return {}

    challenges = (
        Challenge.objects
        .filter(id__in=challenge_ids)
        .select_related(
            'pitch',
            'club',
            'team__logo',
            'challenged_team__logo',
        )
    )

    result: dict[str, UserBookingItem] = {}
    for c in challenges:
        result[str(c.id)] = UserBookingItem(
            entry_type             = 'pending_challenge',
            id                     = c.id,
            date                   = c.date,
            start_time             = c.start_time,
            end_time               = c.end_time,
            final_price            = None,          # no price yet on unlinked challenge
            status                 = c.status,
            created_at             = c.created_at,
            pitch_id               = c.pitch_id,
            pitch_name             = c.pitch.name if c.pitch else None,
            club_id                = c.club_id,
            club_name              = c.club.name if c.club else None,
            challenge_id           = c.id,
            challenge_status       = c.status,
            result_team            = c.result_team,
            result_challenged_team = c.result_challenged_team,
            team_id                = c.team_id,
            team_name              = c.team.name if c.team else None,
            team_logo              = (
                c.team.logo.logo
                if c.team and c.team.logo else None
            ),
            challenged_team_id     = c.challenged_team_id,
            challenged_team_name   = (
                c.challenged_team.name
                if c.challenged_team else None
            ),
            challenged_team_logo   = (
                c.challenged_team.logo.logo
                if c.challenged_team and c.challenged_team.logo else None
            ),
        )

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Public service
# ──────────────────────────────────────────────────────────────────────────────

class UserBookingService:
    """
    Unified, paginated timeline of a player's bookings and pending challenges.

    Usage:
        items, total = UserBookingService.fetch_page(
            user_id=request.user.id,
            arabic_label='مكتمل',   # optional status filter
            limit=10,
            offset=0,
        )
    """

    @staticmethod
    def fetch_page(
        user_id:      str | uuid.UUID,
        arabic_label: str | None = None,
        limit:        int = 10,
        offset:       int = 0,
    ) -> tuple[list[UserBookingItem], int]:

        # Normalise user_id to string; strip dashes on SQLite (stores UUIDs as hex)
        user_id_str = str(user_id)
        if connection.vendor == 'sqlite':
            user_id_str = user_id_str.replace('-', '')

        # ── Resolve status filters ────────────────────────────────────────────
        if arabic_label is not None:
            booking_statuses, challenge_statuses = ARABIC_STATUS_MAP[arabic_label]
        else:
            # No filter: return ALL bookings + any unlinked pending challenges
            booking_statuses   = None                       # no booking-status filter
            challenge_statuses = _UNLINKED_CHALLENGE_STATUSES

        include_bookings   = booking_statuses is None or bool(booking_statuses)
        include_challenges = bool(challenge_statuses)

        # Edge case: both branches skipped (e.g. a filter that maps to nothing)
        if not include_bookings and not include_challenges:
            return [], 0

        # ── Step 1: lightweight paginated ID fetch ────────────────────────────
        id_sql    = _build_id_sql(booking_statuses, challenge_statuses)
        id_params = _build_params(
            user_id_str, booking_statuses, challenge_statuses,
            extra=[limit, offset],
        )

        with connection.cursor() as cur:
            cur.execute(id_sql, id_params)
            cols    = [col[0] for col in cur.description]
            id_rows = [dict(zip(cols, row)) for row in cur.fetchall()]

        if not id_rows:
            return [], 0

        # ── Step 2: total count (no ORDER BY / LIMIT — much cheaper) ──────────
        count_sql    = _build_count_sql(booking_statuses, challenge_statuses)
        count_params = _build_params(user_id_str, booking_statuses, challenge_statuses)

        with connection.cursor() as cur:
            cur.execute(count_sql, count_params)
            total_count: int = cur.fetchone()[0]

        # ── Step 3: hydrate full objects via ORM (IN-list, no N+1) ───────────
        # Normalise IDs to canonical UUID strings (handles SQLite hex vs PG uuid)
        booking_ids   = [
            _to_uuid_str(r['id'])
            for r in id_rows if r['entry_type'] == 'booking'
        ]
        challenge_ids = [
            _to_uuid_str(r['id'])
            for r in id_rows if r['entry_type'] == 'pending_challenge'
        ]

        bookings_map   = _hydrate_bookings(booking_ids)
        challenges_map = _hydrate_challenges(challenge_ids)

        # ── Step 4: re-assemble in the sort order returned by the ID query ────
        results: list[UserBookingItem] = []
        for row in id_rows:
            key  = _to_uuid_str(row['id'])
            item = (
                bookings_map.get(key)
                if row['entry_type'] == 'booking'
                else challenges_map.get(key)
            )
            if item is not None:
                item.total_count = total_count
                results.append(item)

        return results, total_count