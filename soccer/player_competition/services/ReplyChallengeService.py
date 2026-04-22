from django.db import transaction
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from dashboard_booking.services.PricingService import PricingService
from player_competition.services.CreateChallengeService import CreateChallengeService

from ..models import Challenge, ChallengeStatus
from player_booking.models import Booking, BookingStatus, PayStatus
from django.db.models import Count, Q

from player_team.models import Team, TeamMember, MemberStatus
from player_competition.services.challenge_equipment_service import ChallengeEquipmentService


class ReplyChallengeService:
    """
    Handles the captain's reply to a PENDING_TEAM challenge.

    REJECT → status becomes REJECTED  (1 update query)
    ACCEPT → status becomes PENDING_OWNER + Booking created with PENDING_MANAGER (1 update + 1 insert)

    DB hits:
      Reject: 2  (1 fetch + auth,  1 update)
      Accept: 3  (1 fetch + auth,  1 update,  1 insert)  — all inside atomic
    """

    ACCEPT = "accept"
    REJECT = "reject"

    @staticmethod
    def execute(challenge_id, action: str, requesting_user_id) -> Challenge:

        # ── Query 1: single fetch — auth + existence + status check ───────
        # Joining through challenged_team__captain_id means the DB does the
        # permission check; no separate round-trip needed.
        challenge = (
            Challenge.objects
            .select_related("pitch")           # needed for Booking price on accept
            .filter(
                id=challenge_id,
                status=ChallengeStatus.PENDING_TEAM,
                challenged_team__captain_id=requesting_user_id,
            )
            .first()
        )

        if challenge is None:
            # Distinguish "not found" from "wrong person" — both return 404
            # to avoid leaking challenge existence to non-members.
            raise NotFound(detail={"error": "التحدي غير موجود."})

        if action == ReplyChallengeService.REJECT:
            return ReplyChallengeService._reject(challenge)

        if action == ReplyChallengeService.ACCEPT:
            return ReplyChallengeService._accept(challenge)

        raise ValidationError({"error": f"Unknown action '{action}'."})   # defensive; serializer already validates

    # ── Private helpers ────────────────────────────────────────────────────

    @staticmethod
    def _reject(challenge: Challenge) -> Challenge:
        # ── Query 2: targeted UPDATE — no full model save ─────────────────
        Challenge.objects.filter(id=challenge.id).update(
            status=ChallengeStatus.REJECTED,
        )
        challenge.status = ChallengeStatus.REJECTED   # keep in-memory object consistent
        return challenge

    @staticmethod
    def _accept(challenge: Challenge) -> Challenge:
        with transaction.atomic():

            # ── Query 2: one shot — active players + captain of sending team ──
            # Evaluating to a list so we can read captain_id in Python
            # AND pass player_ids to the conflict filter below.
            active_players = list(
                TeamMember.objects.filter(
                    team_id__in=[challenge.team_id, challenge.challenged_team_id],
                    status=MemberStatus.ACTIVE,
                ).values("player_id", "is_captain", "team_id")
            )
            team_1 = challenge.team_id
            team_2 = challenge.challenged_team_id

            players_1 = set()
            players_2 = set()

            for p in active_players:
                if p["team_id"] == team_1:
                    players_1.add(p["player_id"])
                else:
                    players_2.add(p["player_id"])

            if len(players_1) != len(players_2):
                raise ValidationError({"error": "يجب ان يكون الفريقان بنفس عدد الاعبين النشطين"})


            # Captain of the *sending* team — no extra join, no select_related needed.
            captain_id = next(
                (m["player_id"] for m in active_players
                 if m["team_id"] == challenge.team_id and m["is_captain"]),
                None,
            )

            player_ids = [m["player_id"] for m in active_players]

            # ── Query 3: player-level conflict check ──────────────────────
            conflict = Challenge.objects.filter(
                Q(
                    team__teammember__player_id__in=player_ids,
                    team__teammember__status=MemberStatus.ACTIVE,
                ) |
                Q(
                    challenged_team__teammember__player_id__in=player_ids,
                    challenged_team__teammember__status=MemberStatus.ACTIVE,
                ),
                date=challenge.date,
                status__in=[ChallengeStatus.PENDING_OWNER, ChallengeStatus.PENDING_PAY, ChallengeStatus.ACCEPTED],
                start_time__lt=challenge.end_time,
                end_time__gt=challenge.start_time,
            ).exists()

            if conflict:
                raise ValidationError(
                    {"error": "لا يمكن قبول التحدي بسبب تعارض في جدول الحجز لأحد أعضاء الفريقين."}
                )


            # ── Query 5: create linked booking ────────────────────────────
            pitch = challenge.pitch   # already select_related in execute()
            price = PricingService.calculate_final_price(
                pitch, challenge.club_id, challenge.date,
                challenge.start_time, challenge.end_time,
            )

            booking = Booking.objects.create(
                player_id      = captain_id,           # sender's captain — from memory
                pitch_id       = challenge.pitch_id,
                club_id        = challenge.club_id,
                date           = challenge.date,
                start_time     = challenge.start_time,
                end_time       = challenge.end_time,
                price          = price,
                final_price    = price,
                status         = BookingStatus.PENDING_MANAGER,
                payment_status = PayStatus.UNKNOWN,
                is_challenge   = True,
                by_owner       = False,
            )
            # ── Query 6: convert challenge equipments → booking equipments ─
            final_price_with_equipments = CreateChallengeService.convert_to_booking_equipments(
                challenge = challenge,
                booking   = booking,
            )

            if final_price_with_equipments is not None:
                booking.final_price = final_price_with_equipments
                booking.save(update_fields=['final_price', 'updated_at'])   # ── Query 7 (conditional)

            # ── Query 7/8: link booking back to challenge ──────────────────

            # ── Query 4: update challenge status ──────────────────────────
            Challenge.objects.filter(id=challenge.id).update(
                status=ChallengeStatus.PENDING_OWNER,
                booking_id=booking.id
            )
            challenge.status = ChallengeStatus.PENDING_OWNER

            # Challenge.objects.filter(id=challenge.id).update(booking_id=booking.id)
            challenge.booking_id = booking.id


        return challenge