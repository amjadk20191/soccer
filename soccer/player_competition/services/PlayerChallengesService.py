from django.db.models import F, Q
from django.utils import timezone
from player_competition.models import ChallengePlayerBooking, ChallengeStatus

PAST_CHALLENGE_STATUSES = [
    ChallengeStatus.ACCEPTED,
]

def _is_played(time, date):
    return Q(challenge__date__lt=date) | Q(challenge__date=date, challenge__end_time__lte=time)

def _is_upcoming(time, date):
    return Q(challenge__date__gt=date) | Q(challenge__date=date, challenge__start_time__gt=time)

PLAYER_RESULT_FILTERS = {
    'فوز': lambda time, date: (
        _is_played(time, date) & (
            Q(team_id=F('challenge__team_id'),            challenge__result_team__gt=F('challenge__result_challenged_team')) |
            Q(team_id=F('challenge__challenged_team_id'), challenge__result_challenged_team__gt=F('challenge__result_team'))
        )
    ),
    'خسارة': lambda time, date: (
        _is_played(time, date) & (
            Q(team_id=F('challenge__team_id'),            challenge__result_team__lt=F('challenge__result_challenged_team')) |
            Q(team_id=F('challenge__challenged_team_id'), challenge__result_challenged_team__lt=F('challenge__result_team'))
        )
    ),
    'تعادل': lambda time, date: (
        _is_played(time, date) &
        Q(challenge__result_team=F('challenge__result_challenged_team'))
    ),
    'قريباً': lambda time, date: _is_upcoming(time, date),
}


class PlayerChallengesService:

    @staticmethod
    def get_player_challenges(player_id: str, result: str | None = None):
        now = timezone.localtime(timezone.now())
        today = now.date()
        current_time = now.time()

        qs = (
            ChallengePlayerBooking.objects
            .filter(
                player_id=player_id,
                challenge__status__in=PAST_CHALLENGE_STATUSES,
            )
            .select_related('challenge__team__logo', 'challenge__challenged_team__logo')
            .only(
                'id', 'team_id', 'challenge_id',
                'challenge__id',
                'challenge__date', 'challenge__start_time', 'challenge__end_time',
                'challenge__status',
                'challenge__result_team', 'challenge__result_challenged_team',
                'challenge__team_id', 'challenge__team__name', 'challenge__team__logo__logo',
                'challenge__challenged_team_id', 'challenge__challenged_team__name',
                'challenge__challenged_team__logo__logo',
            )
            .order_by('-challenge__date')
        )

        if result in PLAYER_RESULT_FILTERS:
            qs = qs.filter(PLAYER_RESULT_FILTERS[result](current_time, today))

        return qs