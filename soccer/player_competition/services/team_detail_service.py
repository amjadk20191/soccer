
from django.db.models import Prefetch
from rest_framework.exceptions import NotFound

from ..models import Challenge, ChallengeStatus
from player_team.models import Team, TeamMember, MemberStatus


class TeamDetailService:

    @staticmethod
    def get_team_detail(team_id: str) -> Team:

        active_members_prefetch = Prefetch(
            'teammember_set',
            queryset=TeamMember.objects
                .filter(status=MemberStatus.ACTIVE)
                .select_related('player')
                .only(
                    'id', 'is_captain', 'joined_at', 'team_id',
                    'player__id', 'player__full_name', 'player__username',
                    'player__image', 
                ),
            to_attr='active_members',
        )

        # Challenges where this team was either the challenger or the challenged
        sent_challenges_prefetch = Prefetch(
            'sended_challenge',
            queryset=Challenge.objects
                .filter(status=ChallengeStatus.ACCEPTED)
                .select_related('challenged_team__logo')
                .only(
                    'id', 'status', 'date',
                    'result_team', 'result_challenged_team',
                    'team_id',
                    'challenged_team_id',
                    'challenged_team__name',
                    'challenged_team__logo__logo',
                )
                .order_by('-date'),
            to_attr='sent_challenges',
        )

        received_challenges_prefetch = Prefetch(
            'challenge_set',
            queryset=Challenge.objects
                .filter(status=ChallengeStatus.ACCEPTED)
                .select_related('team__logo')
                .only(
                    'id', 'status', 'date',
                    'result_team', 'result_challenged_team',
                    'team_id',
                    'team__name',
                    'team__logo__logo',
                    'challenged_team_id',
                )
                .order_by('-date'),
            to_attr='received_challenges',
        )

        team = (
            Team.objects
            .filter(id=team_id, is_active=True)
            .select_related('logo')
            .prefetch_related(
                active_members_prefetch,
                sent_challenges_prefetch,
                received_challenges_prefetch,
            )
            .only(
                'id', 'name',
                'address', 'time',
                'total_wins', 'total_losses', 'total_draw',
                'total_canceled', 'goals_scored', 'goals_conceded',
                'clean_sheet', 'failed_to_score',
                'logo__logo',
            )
            .first()
        )

        if not team:
            raise NotFound({"error": "الفريق غير موجود."})

        return team