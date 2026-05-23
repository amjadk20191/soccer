# services/booking_detail_service.py

from django.db.models import Prefetch
from rest_framework.exceptions import NotFound, PermissionDenied

from player_competition.models import Challenge, ChallengePlayerBooking
from player_booking.models import Booking, BookingEquipment, BookingStatus
from player_team.models import TeamMember, MemberStatus


class UserBookingDetailService:

    @staticmethod
    def get_booking_detail(booking_id: str, user_id: str) -> Booking:

        challenge_prefetch = Prefetch(
            'challenge_set',
            queryset=Challenge.objects
                .select_related('team__logo', 'challenged_team__logo')
                .only(
                    'id', 'status', 'score_finalized',
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
                    'score_done', 'rate_done',
                    'player__id', 'player__full_name',
                    'player__username', 'player__image',
                ),
            to_attr='challenge_players',
        )

        booking_equipment_prefetch = Prefetch(
            "bookingequipment_set",
            queryset=BookingEquipment.objects.select_related("equipment_def").only(
                "id", "booking_id", "quantity", "price",
                "equipment_def__id", "equipment_def__name",
                # "equipment_def__description",
            )
        )

        booking = (
            Booking.objects
            .filter(id=booking_id)
            .select_related('pitch', 'club', 'coupon')
            .prefetch_related(challenge_prefetch, players_prefetch, booking_equipment_prefetch)
            .only(
                'id',
                'date', 'start_time', 'end_time',
                'price', 'final_price', 'deposit',
                'status', 'payment_status',
                'is_challenge', 'rate_done',
                'player_id',
                'pitch_id', 'pitch__name',
                'club_id', 'club__name',
                'coupon_id', 'created_at',
                'coupon__code', 'coupon__discount_type', 'coupon__discount_value',
            )
            .first()
        )

        if not booking:
            raise NotFound({"error": "الحجز غير موجود."})

        is_direct_booker = str(booking.player_id) == str(user_id)


        if not is_direct_booker:
            raise PermissionDenied({"error": "ليس لديك صلاحية لعرض هذا الحجز."})

        # ── resolve player's team side ─────────────────────────────────────────
        booking._player_team_id = None  # default

        if booking.is_challenge and booking.challenges:
            challenge = booking.challenges[0]
            is_challenge_player = False

            if booking.status == BookingStatus.PENDING_MANAGER:
                # player not yet in ChallengePlayerBooking → look in TeamMember
                member = (
                    TeamMember.objects
                    .filter(
                        player_id=user_id,
                        team_id__in=[challenge.team_id, challenge.challenged_team_id],
                        status=MemberStatus.ACTIVE,
                    )
                    .only('team_id')
                    .first()
                )
                if member:
                    booking._player_team_id = str(member.team_id)
                    is_challenge_player = True

            else:
                # player already registered in ChallengePlayerBooking (already prefetched)
                for cp in booking.challenge_players:
                    if str(cp.player_id) == str(user_id):
                        booking._player_team_id = str(cp.team_id)
                        is_challenge_player = True
                        break
            
            if not is_challenge_player:
                raise PermissionDenied({"error": "ليس لديك صلاحية لعرض هذا الحجز."})
                    
        return booking