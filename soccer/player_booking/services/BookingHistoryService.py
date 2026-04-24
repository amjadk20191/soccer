# services/booking_service.py

from django.db.models import Q, Prefetch

from player_competition.models import Challenge
from player_booking.models import Booking


class UserBookingService:


    @staticmethod
    def get_user_bookings(user_id: str, status: int | None = None):
        challenge_prefetch = Prefetch(
            'challenge_set',
            queryset=Challenge.objects
                .select_related(
                    'team__logo',
                    'challenged_team__logo',
                )
                .only(
                    'id',
                    'result_team', 'result_challenged_team',
                    'team_id', 'team__name', 'team__logo__logo',
                    'challenged_team_id', 'challenged_team__name', 'challenged_team__logo__logo',
                ),
            to_attr='challenges',
        )
        print("user_id",user_id)
        qs = (
            Booking.objects
            .filter(
                Q(player_id=user_id) |
                Q(challengeplayerbooking__player_id=user_id)
            )
            .select_related('pitch', 'club')
            .prefetch_related(challenge_prefetch)
            .only(
                'id',
                'date', 'start_time', 'end_time',
                'final_price',
                'status',
                'pitch_id', 'club_id', 'player_id', 'club__name', 'pitch__name'
            )
            .distinct()
            .order_by('-created_at')
        )

        if status is not None:
            qs = qs.filter(status=status)

        return qs