from django.db.models import F, Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from player_competition.models import Challenge, ChallengeStatus

PAST_CHALLENGE_STATUSES = [
    ChallengeStatus.ACCEPTED,
]

# Shared helper: challenge date/time has already ended
def _is_played(time, date):
    return Q(date__lt=date) | Q(date=date, end_time__lte=time)

# Shared helper: challenge hasn't started yet
def _is_upcoming(time, date):
    return Q(date__gt=date) | Q(date=date, start_time__gt=time)


TEAM_RESULT_FILTERS = {
    # Won: played + team scored more
    'فوز': lambda team_id, time, date: (
        _is_played(time, date) & (
            Q(team_id=team_id,            result_team__gt=F('result_challenged_team')) |
            Q(challenged_team_id=team_id, result_challenged_team__gt=F('result_team'))
        )
    ),
    # Lost: played + team scored less
    'خسارة': lambda team_id, time, date: (
        _is_played(time, date) & (
            Q(team_id=team_id,            result_team__lt=F('result_challenged_team')) |
            Q(challenged_team_id=team_id, result_challenged_team__lt=F('result_team'))
        )
    ),
    # Draw: played + scores are equal + team is participant
    'تعادل': lambda team_id, time, date: (
        _is_played(time, date) &
        Q(result_team=F('result_challenged_team'))
    ),
    # Upcoming: date/time hasn't arrived yet + team is participant
    'قريباً': lambda team_id, time, date: (
        _is_upcoming(time, date)),
}


class TeamChallengesService:
    @staticmethod
    def get_team_challenges(team_id: str, result: str | None = None):
        now = timezone.localtime(timezone.now())
        today = now.date()
        current_time = now.time()

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
            qs = qs.filter(TEAM_RESULT_FILTERS[result](team_id, current_time, today))

        return qs