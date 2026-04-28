from django.db.models import Avg, Count, Q, Subquery, OuterRef
from django.db.models.functions import ExtractYear, Now
from rest_framework.exceptions import ValidationError
from django.conf import settings

from player_team.models import Team, TeamMember, MemberStatus
 
class ShowChallengeTeamService:

    @staticmethod
    def get_challenge_teams(team_id: str, user_id: str, *, name: str | None = None, min_avg_age: int | None = None, max_avg_age: int | None = None):

        if not Team.objects.filter(id=team_id, captain_id=user_id).exists():
            raise ValidationError({"error": "حصرًا للقائد فقط."})

        conflicting_team_ids = (
            TeamMember.objects
            .filter(
                status=MemberStatus.ACTIVE,
                player__teammember__team_id=team_id,
                player__teammember__status=MemberStatus.ACTIVE,
            )
            .values('team_id')
            .distinct()
        )

        active_members_q = Q(teammember__status=MemberStatus.ACTIVE)

        qs = (
            Team.objects
            .filter(challenge_mode=True, is_active=True)
            .exclude(id__in=conflicting_team_ids)
            .select_related('logo')
            .annotate(
                active_member_count=Count('teammember', filter=active_members_q, distinct=True),
                avg_player_age=Avg(
                    ExtractYear(Now()) - ExtractYear('teammember__player__birthday'),
                    filter=active_members_q,
                ),
            )
            .filter(active_member_count__gte=settings.MIN_TEAM_MEMBERS_FOR_CHALLENGE)
            .only(
                'id', 'name',
                'goals_scored', 'total_wins', 'total_losses',
                'created_at',
                'logo__logo',
            )
            .order_by('-total_wins', '-goals_scored')
        )

        if name:
            qs = qs.filter(name__icontains=name)
    
        if min_avg_age is not None:
            qs = qs.filter(avg_player_age__gte=min_avg_age) 

        if max_avg_age is not None:
            qs = qs.filter(avg_player_age__lte=max_avg_age)

        return qs