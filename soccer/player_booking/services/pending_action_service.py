from django.db.models import BooleanField, Case, Exists, OuterRef, Q, Value, When
from player_booking.models import Booking, BookingStatus
from player_competition.models import ChallengePlayerBooking


class PendingActionService:

    @staticmethod
    def get_pending_actions(user) -> list:
        cp_base = ChallengePlayerBooking.objects.filter(
            booking=OuterRef('pk'),
            player=user,
        )

        needs_rate_sq  = cp_base.filter(rate_done=False)
        needs_score_sq = cp_base.filter(score_done=False)

        return (
            Booking.objects
            .filter(status=BookingStatus.COMPLETED)
            .filter(
                Q(Q(is_challenge=False, player=user, rate_done=False))
                |
                Q(Q(is_challenge=True) & (Exists(needs_rate_sq) | Exists(needs_score_sq)))
            )
            .annotate(
                make_rate=Case(
                    When(is_challenge=False, then=Value(True)),
                    When(is_challenge=True,  then=Exists(needs_rate_sq)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
                make_score=Case(
                    When(is_challenge=True, then=Exists(needs_score_sq)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
            )
            .select_related('pitch', 'club')
            .only(
                'id',
                'date',
                'start_time',
                'end_time',
                'is_challenge',
                'pitch__name',
                'club__name',
            )
            .order_by('-date', '-start_time')
        )