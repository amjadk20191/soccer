
from django.db.models import Prefetch
from rest_framework.exceptions import NotFound

from player_competition.models import Challenge, ChallengePlayerBooking


class ChallengeDetailService:

    @staticmethod
    def get_challenge_detail(challenge_id: str) -> Challenge:

        players_prefetch = Prefetch(
            'challengeplayerbooking_set',
            queryset=ChallengePlayerBooking.objects
                .select_related('player')
                .only(
                    'id', 'team_id', 'challenge_id',
                    'player__id', 'player__full_name',
                    'player__username', 'player__image',
                ),
            to_attr='challenge_players',
        )

        challenge = (
            Challenge.objects
            .filter(id=challenge_id)
            .select_related(
                'team__logo',
                'challenged_team__logo',
                'pitch',
                'club',
            )
            .prefetch_related(players_prefetch)
            .only(
                'id', 'date',
                'start_time', 'end_time',
                'result_team', 'result_challenged_team',
                'team_id', 'team__name', 'team__logo__logo',
                'challenged_team_id', 'challenged_team__name', 'challenged_team__logo__logo',
                'pitch_id', 'pitch__name',
                'club_id', 'club__name',
            )
            .first()
        )

        if not challenge:
            raise NotFound({"error": "التحدي غير موجود."})

        return challenge