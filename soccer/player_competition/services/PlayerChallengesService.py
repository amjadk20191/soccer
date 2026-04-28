
from django.db.models import F, Q
from rest_framework.exceptions import NotFound, ValidationError

from player_competition.models import ChallengePlayerBooking, ChallengeStatus


PAST_CHALLENGE_STATUSES = [
    
    ChallengeStatus.ACCEPTED,
    ChallengeStatus.CANCELED,
    ChallengeStatus.NO_SHOW,
    ChallengeStatus.DISPUTED_SCORE,
    ChallengeStatus.DISPUTED,
]

# Result-based filters (require scores to exist)

PLAYER_RESULT_FILTERS = {
    'فاز': (
        Q(challenge__result_team__isnull=False, challenge__result_challenged_team__isnull=False) & (
            Q(team_id=F('challenge__team_id'),            challenge__result_team__gt=F('challenge__result_challenged_team')) |
            Q(team_id=F('challenge__challenged_team_id'), challenge__result_challenged_team__gt=F('challenge__result_team'))
        )
    ),
    'خسر': (
        Q(challenge__result_team__isnull=False, challenge__result_challenged_team__isnull=False) & (
            Q(team_id=F('challenge__team_id'),            challenge__result_team__lt=F('challenge__result_challenged_team')) |
            Q(team_id=F('challenge__challenged_team_id'), challenge__result_challenged_team__lt=F('challenge__result_team'))
        )
    ),
    'تعادل': Q(
        challenge__result_team__isnull=False,
        challenge__result_challenged_team__isnull=False,
        challenge__result_team=F('challenge__result_challenged_team'),
    ),
    'قريبا': Q(                     # ← new
        challenge__status=ChallengeStatus.ACCEPTED,
        challenge__result_team__isnull=True,
        challenge__result_challenged_team__isnull=True,
    ),
}



PLAYER_STATUS_FILTERS = {
    'ملغى':              Q(challenge__status=ChallengeStatus.CANCELED),
    'لم يحضر':          Q(challenge__status=ChallengeStatus.NO_SHOW),
    'مشكلة في النتيجة': Q(challenge__status=ChallengeStatus.DISPUTED_SCORE),
    'مشكلة':            Q(challenge__status=ChallengeStatus.DISPUTED),
}



class PlayerChallengesService:

    @staticmethod
    def get_player_challenges(player_id: str, result: str | None = None):
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
            qs = qs.filter(PLAYER_RESULT_FILTERS[result])
        elif result in PLAYER_STATUS_FILTERS:
            qs = qs.filter(PLAYER_STATUS_FILTERS[result])

        return qs