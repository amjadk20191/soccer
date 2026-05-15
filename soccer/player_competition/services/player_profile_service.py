
from django.db.models import Prefetch
from rest_framework.exceptions import NotFound

from player_competition.models import ChallengePlayerBooking, Challenge, ChallengeStatus
from django.contrib.auth import get_user_model

from player_team.models import MemberStatus, Request, TeamMember

User = get_user_model()


class PlayerProfileService:

    @staticmethod
    def get_player_profile(player_id: str, team_id: str = None):

        played_challenges_prefetch = Prefetch(
            'challengeplayerbooking_set',
            queryset=ChallengePlayerBooking.objects
                .select_related(
                    'challenge__team__logo',
                    'challenge__challenged_team__logo',
                )
                .only(
                    'id', 'team_id', 'challenge_id',
                    'challenge__id',
                    'challenge__start_time',
                    'challenge__end_time',
                    'challenge__result_team',
                    'challenge__result_challenged_team',
                    'challenge__date',
                    'challenge__team_id',
                    'challenge__team__name',
                    'challenge__team__logo__logo',
                    'challenge__challenged_team_id',
                    'challenge__challenged_team__name',
                    'challenge__challenged_team__logo__logo',
                )
                .filter(challenge__status=ChallengeStatus.ACCEPTED)
                .order_by('-challenge__date')[:3],
            to_attr='played_challenges',
        )

        player = (
            User.objects
            .filter(id=player_id, is_active=True)
            .prefetch_related(played_challenges_prefetch)
            .only(
                'id', 'full_name', 'username',
                'image', 'birthday',
                'height', 'weight', 'foot_preference',
                'booking_time', 'cancel_time', 'disputed_time', 'no_show_time', 'expired_time',
                'challenge_time', 'challenge_wins', 'challenge_losses', 'challenge_draw',
                'governorate'
            )
            .first()
        )

        if not player:
            raise NotFound({"error": "اللاعب غير موجود."})

        # --- optional team context (2 lean queries, only when team_id supplied) ---
        team_context = {'in_team': None, 'request_id': None}

        if team_id:
            in_team = TeamMember.objects.filter(
                team_id=team_id,
                player_id=player_id,
                status__in=[MemberStatus.ACTIVE, MemberStatus.INACTIVE],
            ).exists()

            pending_id = (
                Request.objects
                .filter(
                    team_id=team_id,
                    player_id=player_id,
                    status=1,       #Pending
                    recruitment_post__isnull=True,
                )
                .values_list('id', flat=True)
                .first()
            )

            team_context = {
                'in_team': in_team,
                'request_id': str(pending_id) if pending_id else None,
            }

        return player, team_context