# services/booking_detail_service.py

from django.db.models import Prefetch
from rest_framework.exceptions import NotFound, PermissionDenied

from player_competition.models import Challenge, ChallengePlayerBooking
from player_booking.models import Booking, BookingEquipment


class UserBookingDetailService:

    @staticmethod
    def get_booking_detail(booking_id: str, user_id: str) -> Booking:

        challenge_prefetch = Prefetch(
            'challenge_set',
            queryset=Challenge.objects
                .select_related('team__logo', 'challenged_team__logo')
                .only(
                    'id', 'status',
                    'result_team', 'result_challenged_team',
                    'team_id', 'team__name', 'team__logo__logo',
                    'challenged_team_id', 'challenged_team__name', 'challenged_team__logo__logo',
                ),
            to_attr='challenges',
        )

        players_prefetch = Prefetch(
            'challengeplayerbooking_set',
            queryset=ChallengePlayerBooking.objects
                .select_related('player', 'team')
                .only(
                    'id', 'team_id',
                    'player__id', 'player__full_name',
                    'player__username', 'player__image',
                ),
            to_attr='challenge_players',
        )
        booking_equipment_prefetch = Prefetch(
            "bookingequipment_set",
            queryset=BookingEquipment.objects.select_related("equipment_def").only(
                "id",
                "booking_id",
                "quantity",
                "equipment_def__id",
                "equipment_def__name",
                "equipment_def__description",
                "equipment_def__image",
            )
        )

        booking = (
            Booking.objects
            .filter(id=booking_id)
            .select_related('pitch', 'club')
            .prefetch_related(challenge_prefetch, players_prefetch, booking_equipment_prefetch)
            .only(
                'id',
                'date', 'start_time', 'end_time',
                'price', 'final_price', 'deposit',
                'status', 'payment_status',
                'is_challenge',
                'player_id',
                'pitch_id', 'pitch__name',
                'club_id', 'club__name',
            )
            .first()
        )

        if not booking:
            raise NotFound({"error": "الحجز غير موجود."})

        is_direct_booker   = str(booking.player_id) == str(user_id)
        is_challenge_player = any(
            str(cp.player_id) == str(user_id)
            for cp in booking.challenge_players   # already prefetched — no DB hit
        )

        if not is_direct_booker and not is_challenge_player:
            raise PermissionDenied({"error": "ليس لديك صلاحية لعرض هذا الحجز."})

        return booking