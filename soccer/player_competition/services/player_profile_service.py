
from django.db.models import Prefetch
from rest_framework.exceptions import NotFound

from player_competition.models import ChallengePlayerBooking, Challenge, ChallengeStatus
from django.contrib.auth import get_user_model

User = get_user_model()


class PlayerProfileService:

    @staticmethod
    def get_player_profile(player_id: str):

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
                    'challenge__status',
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
                .filter(
                    challenge__status=ChallengeStatus.ACCEPTED  # only finished challenges
                )
                .order_by('-challenge__date'),
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
                'booking_time', 'cancel_time',
            )
            .first()
        )

        if not player:
            raise NotFound({"error": "اللاعب غير موجود."})
        print(player)

        return player