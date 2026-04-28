# services/booking_service.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import uuid

from django.db import connection

from player_booking.models import Booking, BookingStatus
from player_competition.models import Challenge, ChallengePlayerBooking, ChallengeStatus
from player_team.models import Team, TeamMember, MemberStatus

# ── table names ───────────────────────────────────────────────────────────────
_TB   = Booking._meta.db_table
_TC   = Challenge._meta.db_table
_TCPB = ChallengePlayerBooking._meta.db_table
_TM   = TeamMember._meta.db_table
_TT   = Team._meta.db_table
_TI   = Team._meta.get_field('logo').related_model._meta.db_table
_TP   = Booking._meta.get_field('pitch').related_model._meta.db_table
_TCL  = Booking._meta.get_field('club').related_model._meta.db_table


# ── Unified Arabic label → (booking_statuses, challenge_statuses) ─────────────
# [] on either side = skip that branch entirely
# None for booking_statuses = no filter (show all bookings)
StatusFilter = tuple[list[int] | None, list[int]]

ARABIC_STATUS_MAP: dict[str, StatusFilter] = {
    'بانتظار_التأكيد_النادي':                    ([BookingStatus.PENDING_MANAGER], [ChallengeStatus.PENDING_OWNER]),
    'وقت_مقترح_جديد':                            ([BookingStatus.PENDING_PLAYER],  []),
    'مشكلة_في_النتيجة':                          ([],                              [ChallengeStatus.DISPUTED_SCORE]),
    'بانتظار_الفريق_المنافس':                    ([],                              [ChallengeStatus.PENDING_TEAM]),
    'بانتظار_الدفع':                             ([BookingStatus.PENDING_PAY],     [ChallengeStatus.PENDING_PAY]),
    'مكتمل':                                     ([BookingStatus.COMPLETED],       [ChallengeStatus.ACCEPTED]),
    'ملغى':                                      ([BookingStatus.CANCELED],        [ChallengeStatus.CANCELED]),
    'لم_تحضر':                                   ([BookingStatus.NO_SHOW],         [ChallengeStatus.NO_SHOW]),
    'مشكلة':                                     ([BookingStatus.DISPUTED],        [ChallengeStatus.DISPUTED]),
    'انتهت_صلاحيته':                             ([BookingStatus.EXPIRED],         [ChallengeStatus.EXPIRED]),
}


# ── Reverse map: (entry_type, status_int) → Arabic label ─────────────────────
_BOOKING_STATUS_TO_ARABIC:   dict[int, str] = {}
_CHALLENGE_STATUS_TO_ARABIC: dict[int, str] = {}

for _label, (_b_statuses, _c_statuses) in ARABIC_STATUS_MAP.items():
    if _b_statuses:
        for _s in _b_statuses:
            _BOOKING_STATUS_TO_ARABIC[_s] = _label
    if _c_statuses:
        for _s in _c_statuses:
            _CHALLENGE_STATUS_TO_ARABIC[_s] = _label


# All valid Arabic labels exposed to views for validation
VALID_ARABIC_STATUSES: list[str] = list(ARABIC_STATUS_MAP.keys())


_NO_FILTER_CHALLENGE_STATUSES = [ChallengeStatus.PENDING_TEAM, ChallengeStatus.DISPUTED_SCORE, 
                                ChallengeStatus.PENDING_OWNER, ChallengeStatus.PENDING_PAY, 
                                ChallengeStatus.ACCEPTED, ChallengeStatus.CANCELED,
                                ChallengeStatus.NO_SHOW, ChallengeStatus.DISPUTED, ChallengeStatus.EXPIRED]


def _ph(n: int) -> str:
    """Generate n comma-separated %s placeholders."""
    return ', '.join(['%s'] * n)


def _build_sql(
    filter_booking_statuses: list[int] | None,  # None = no filter, [] = skip branch
    challenge_statuses: list[int],               # [] = skip branch
) -> str:
    include_bookings   = filter_booking_statuses is None or len(filter_booking_statuses) > 0
    include_challenges = len(challenge_statuses) > 0

    booking_status_clause = (
        f'AND b.status IN ({_ph(len(filter_booking_statuses))})'
        if filter_booking_statuses else ''
    )
    
    booking_branch = f"""
        SELECT
            b.id,
            'booking'  AS entry_type,
            b.created_at
        FROM {_TB} b
        WHERE (
            b.player_id = %s
            OR EXISTS (
                SELECT 1 FROM {_TCPB} cpb
                WHERE  cpb.booking_id = b.id
                AND    cpb.player_id  = %s
            )
        )
        {booking_status_clause}
    """ if include_bookings else None

    challenge_branch = f"""
        SELECT
            c.id,
            'pending_challenge' AS entry_type,
            c.created_at
        FROM {_TC} c
        WHERE c.status IN ({_ph(len(challenge_statuses))})
          AND (
              EXISTS (
                  SELECT 1 FROM {_TM} tm
                  WHERE  tm.team_id   = c.team_id
                  AND    tm.player_id = %s
                  AND    tm.status    = %s
              )
              OR EXISTS (
                  SELECT 1 FROM {_TM} tm
                  WHERE  tm.team_id   = c.challenged_team_id
                  AND    tm.player_id = %s
                  AND    tm.status    = %s
              )
          )
    """ if include_challenges else None

    branches = ' UNION ALL '.join(b for b in [booking_branch, challenge_branch] if b is not None)

    return f"""
        WITH paged AS (
            SELECT
                id,
                entry_type,
                created_at,
                COUNT(*) OVER () AS total_count
            FROM ({branches}) combined
            ORDER BY created_at DESC
            LIMIT  %s
            OFFSET %s
        )
        SELECT
            pg.entry_type,
            pg.total_count,

            b.id            AS id,
            b.date          AS date,
            b.start_time    AS start_time,
            b.end_time      AS end_time,
            b.final_price   AS final_price,
            b.status        AS status,
            b.created_at    AS created_at,
            b.pitch_id      AS pitch_id,
            pit.name        AS pitch_name,
            b.club_id       AS club_id,
            clu.name        AS club_name,
            bch.id          AS challenge_id,
            bch.status      AS challenge_status,
            bch.result_team              AS result_team,
            bch.result_challenged_team   AS result_challenged_team,
            bt.id           AS team_id,
            bt.name         AS team_name,
            bti.logo        AS team_logo,
            bct.id          AS challenged_team_id,
            bct.name        AS challenged_team_name,
            bcti.logo       AS challenged_team_logo,

            pc.id           AS pc_id,
            pc.date         AS pc_date,
            pc.start_time   AS pc_start_time,
            pc.end_time     AS pc_end_time,
            pc.status       AS pc_status,
            pc.created_at   AS pc_created_at,
            pc.result_team              AS pc_result_team,
            pc.result_challenged_team   AS pc_result_challenged_team,
            pc.pitch_id     AS pc_pitch_id,
            pcpit.name      AS pc_pitch_name,
            pc.club_id      AS pc_club_id,
            pcclu.name      AS pc_club_name,
            pt.id           AS pc_team_id,
            pt.name         AS pc_team_name,
            pti.logo        AS pc_team_logo,
            pct.id          AS pc_challenged_team_id,
            pct.name        AS pc_challenged_team_name,
            pcti.logo       AS pc_challenged_team_logo

        FROM paged pg

        LEFT JOIN {_TB}  b    ON b.id    = pg.id AND pg.entry_type = 'booking'
        LEFT JOIN {_TP}  pit  ON pit.id  = b.pitch_id
        LEFT JOIN {_TCL} clu  ON clu.id  = b.club_id
        LEFT JOIN {_TC}  bch  ON bch.booking_id = b.id
        LEFT JOIN {_TT}  bt   ON bt.id   = bch.team_id
        LEFT JOIN {_TI}  bti  ON bti.id  = bt.logo_id
        LEFT JOIN {_TT}  bct  ON bct.id  = bch.challenged_team_id
        LEFT JOIN {_TI}  bcti ON bcti.id = bct.logo_id

        LEFT JOIN {_TC}  pc    ON pc.id    = pg.id AND pg.entry_type = 'pending_challenge'
        LEFT JOIN {_TP}  pcpit ON pcpit.id = pc.pitch_id
        LEFT JOIN {_TCL} pcclu ON pcclu.id = pc.club_id
        LEFT JOIN {_TT}  pt    ON pt.id    = pc.team_id
        LEFT JOIN {_TI}  pti   ON pti.id   = pt.logo_id
        LEFT JOIN {_TT}  pct   ON pct.id   = pc.challenged_team_id
        LEFT JOIN {_TI}  pcti  ON pcti.id  = pct.logo_id
    """


@dataclass
class UserBookingItem:
    entry_type:             str
    id:                     Any
    date:                   Any
    start_time:             Any
    end_time:               Any
    final_price:            Any
    status:                 Any
    created_at:             Any
    pitch_id:               Any
    pitch_name:             Any
    club_id:                Any
    club_name:              Any
    challenge_id:           Any
    challenge_status:       Any
    result_team:            Any
    result_challenged_team: Any
    team_id:                Any
    team_name:              Any
    team_logo:              Any
    challenged_team_id:     Any
    challenged_team_name:   Any
    challenged_team_logo:   Any
    total_count:            int = 0

    def get_status_display(self) -> str | None:
        if self.entry_type == 'booking' and self.status is not None:
            return _BOOKING_STATUS_TO_ARABIC.get(self.status)
        if self.entry_type == 'pending_challenge' and self.status is not None:
            return _CHALLENGE_STATUS_TO_ARABIC.get(self.status)
        return None


def _normalize(row: dict) -> UserBookingItem:
    if row['entry_type'] == 'booking':
        return UserBookingItem(
            entry_type             = 'booking',
            id                     = uuid.UUID(row['id']),
            date                   = row['date'],
            start_time             = row['start_time'],
            end_time               = row['end_time'],
            final_price            = row['final_price'],
            status                 = row['status'],
            created_at             = row['created_at'],
            pitch_id               = row['pitch_id'],
            pitch_name             = row['pitch_name'],
            club_id                = row['club_id'],
            club_name              = row['club_name'],
            challenge_id           = row['challenge_id'],
            challenge_status       = row['challenge_status'],
            result_team            = row['result_team'],
            result_challenged_team = row['result_challenged_team'],
            team_id                = row['team_id'],
            team_name              = row['team_name'],
            team_logo              = row['team_logo'],
            challenged_team_id     = row['challenged_team_id'],
            challenged_team_name   = row['challenged_team_name'],
            challenged_team_logo   = row['challenged_team_logo'],
            total_count            = row['total_count'],
        )
    return UserBookingItem(
        entry_type             = 'pending_challenge',
        id                     = uuid.UUID(row['pc_id']),             
        date                   = row['pc_date'],
        start_time             = row['pc_start_time'],
        end_time               = row['pc_end_time'],
        final_price            = None,
        status                 = row['pc_status'],
        created_at             = row['pc_created_at'],
        pitch_id               = row['pc_pitch_id'],
        pitch_name             = row['pc_pitch_name'],
        club_id                = row['pc_club_id'],
        club_name              = row['pc_club_name'],
        challenge_id           = row['pc_id'],
        challenge_status       = row['pc_status'],
        result_team            = row['pc_result_team'],
        result_challenged_team = row['pc_result_challenged_team'],
        team_id                = row['pc_team_id'],
        team_name              = row['pc_team_name'],
        team_logo              = row['pc_team_logo'],
        challenged_team_id     = row['pc_challenged_team_id'],
        challenged_team_name   = row['pc_challenged_team_name'],
        challenged_team_logo   = row['pc_challenged_team_logo'],
        total_count            = row['total_count'],
    )


class UserBookingService:

    @staticmethod
    def fetch_page(
        user_id:      str,
        arabic_label: str | None = None,  # None = no filter
        limit:        int = 10,
        offset:       int = 0,
    ) -> tuple[list[UserBookingItem], int]:

        user_id = str(user_id)
        if connection.vendor == 'sqlite':
            user_id = user_id.replace('-', '')

        # Resolve Arabic label → status lists
        if arabic_label is not None:
            booking_statuses, challenge_statuses = ARABIC_STATUS_MAP[arabic_label]
        else:
            booking_statuses   = None                           # no filter on bookings
            challenge_statuses = _NO_FILTER_CHALLENGE_STATUSES  # pending only

        include_bookings   = booking_statuses is None or len(booking_statuses) > 0
        include_challenges = len(challenge_statuses) > 0

        sql = _build_sql(
            filter_booking_statuses=booking_statuses,
            challenge_statuses=challenge_statuses,
        )

        params: list[Any] = []

        if include_bookings:
            params.extend([user_id, user_id])
            if booking_statuses:
                params.extend(booking_statuses)

        if include_challenges:
            params.extend(challenge_statuses)
            params.extend([user_id, MemberStatus.ACTIVE, user_id, MemberStatus.ACTIVE])

        params.extend([limit, offset])

        with connection.cursor() as cur:
            cur.execute(sql, params)
            cols = [col[0] for col in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]

        if not rows:
            return [], 0

        return [_normalize(r) for r in rows], rows[0]['total_count']