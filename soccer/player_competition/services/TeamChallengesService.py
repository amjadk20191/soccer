from django.db.models import F, Q
from rest_framework.exceptions import NotFound, ValidationError

from player_competition.models import Challenge, ChallengeStatus


PAST_CHALLENGE_STATUSES = [
    ChallengeStatus.ACCEPTED,
    ChallengeStatus.CANCELED,
    ChallengeStatus.NO_SHOW,
    ChallengeStatus.DISPUTED_SCORE,
    ChallengeStatus.DISPUTED,
]

# Result-based filters (require scores to exist)
TEAM_RESULT_FILTERS = {
    'فاز': lambda team_id: (
        Q(result_team__isnull=False, result_challenged_team__isnull=False) & (
            Q(team_id=team_id,            result_team__gt=F('result_challenged_team')) |
            Q(challenged_team_id=team_id, result_challenged_team__gt=F('result_team'))
        )
    ),
    'خسر': lambda team_id: (
        Q(result_team__isnull=False, result_challenged_team__isnull=False) & (
            Q(team_id=team_id,            result_team__lt=F('result_challenged_team')) |
            Q(challenged_team_id=team_id, result_challenged_team__lt=F('result_team'))
        )
    ),
    'تعادل': lambda _: Q(
        result_team__isnull=False,
        result_challenged_team__isnull=False,
        result_team=F('result_challenged_team'),
    ),
    'قريبا': lambda _: Q(           # ← new
        status=ChallengeStatus.ACCEPTED,
        result_team__isnull=True,
        result_challenged_team__isnull=True,
    ),
}

# Status-based filters
TEAM_STATUS_FILTERS = {
    'ملغى':              Q(status=ChallengeStatus.CANCELED),
    'لم يحضر':          Q(status=ChallengeStatus.NO_SHOW),
    'مشكلة في النتيجة': Q(status=ChallengeStatus.DISPUTED_SCORE),
    'مشكلة':            Q(status=ChallengeStatus.DISPUTED),
}


VALID_RESULTS = set(TEAM_RESULT_FILTERS) | set(TEAM_STATUS_FILTERS)


class TeamChallengesService:

    @staticmethod
    def get_team_challenges(team_id: str, result: str | None = None):
        qs = (
            Challenge.objects
            .filter(
                Q(team_id=team_id) | Q(challenged_team_id=team_id),
                status__in=PAST_CHALLENGE_STATUSES,
            )
            .select_related('team__logo', 'challenged_team__logo')
            .only(
                'id', 'date', 'start_time', 'end_time',
                'status',
                'result_team', 'result_challenged_team',
                'team_id', 'team__name', 'team__logo__logo',
                'challenged_team_id', 'challenged_team__name', 'challenged_team__logo__logo',
            )
            .order_by('-date')
        )

        if result in TEAM_RESULT_FILTERS:
            qs = qs.filter(TEAM_RESULT_FILTERS[result](team_id))
        elif result in TEAM_STATUS_FILTERS:
            qs = qs.filter(TEAM_STATUS_FILTERS[result])

        return qs