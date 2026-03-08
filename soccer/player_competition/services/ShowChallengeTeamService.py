from django.db.models import Avg, Count, Q, Subquery, OuterRef
from django.db.models.functions import ExtractYear, Now
from rest_framework.exceptions import ValidationError

from player_team.models import Team, TeamMember, MemberStatus
 
class ShowChallengeTeamService:

    @staticmethod
    def get_challenge_teams(team_id: str, user_id: str):
        print(team_id, user_id)
        is_captain=Team.objects.filter(id=team_id, captain_id=user_id).exists()
        if not is_captain:
            raise ValidationError("Only the team captain can see teams.")


        # ✅ Single-level subquery instead of nested — one JOIN in SQL
        conflicting_team_ids = (
            TeamMember.objects
            .filter(
                status=MemberStatus.ACTIVE,
                player__teammember__team_id=team_id,          # traverse relation directly
                player__teammember__status=MemberStatus.ACTIVE,
            )
            .values('team_id')
            .distinct()
        )

        active_members_q = Q(teammember__status=MemberStatus.ACTIVE)

        return (
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
            .only(
                'id', 'name',
                'goals_scored', 'total_wins', 'total_losses',
                'created_at',
                'logo__logo',
            )
            .order_by('-total_wins', '-goals_scored')
        )