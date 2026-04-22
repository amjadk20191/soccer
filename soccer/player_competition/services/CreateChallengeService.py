from django.db import transaction
from django.db.models import Count, Q
from soccer.enm import BOOKING_STATUS_DENIED
from django.conf import settings

from ..models import Challenge, ChallengeStatus,ChallengeEquipment
from player_team.models import Team, TeamMember, MemberStatus
from dashboard_manage.models import Pitch
from rest_framework.exceptions import ValidationError
from dashboard_booking.services.EquipmentBookingService import EquipmentBookingService

from decimal import Decimal
from dashboard_manage.models import ClubEquipment
from player_booking.models import BookingEquipment, Booking
class CreateChallengeService:



    @staticmethod
    def convert_to_booking_equipments(challenge: Challenge, booking: Booking) -> Decimal | None:
        """
        Converts ChallengeEquipment rows into BookingEquipment rows
        by reusing EquipmentBookingService.Create_Equipment_Booking.

        Returns updated final_price if equipments exist, None otherwise.
        Called inside _accept — must be within the same atomic block.
        """
        challenge_equipments = (
            ChallengeEquipment.objects
            .filter(challenge_id=challenge.id)
            .values('equipment_id', 'quantity')   # lightweight — no model instantiation
        )

        if not challenge_equipments:
            return None

        # Reshape to the format Create_Equipment_Booking expects: [{'id': ..., 'quantity': ...}]
        equipments_payload = [
            {'id': row['equipment_id'], 'quantity': row['quantity']}
            for row in challenge_equipments
        ]

        # Reuse existing service — handles quantity conflict checks + bulk insert
        final_price = EquipmentBookingService.Create_Equipment_Booking(
            club_id    = challenge.club_id,
            booking    = booking,
            equipments = equipments_payload,
            start_time = challenge.start_time,
            end_time   = challenge.end_time,
        )

        return final_price

    @staticmethod
    def create(validated_data: dict, requesting_user_id) -> Challenge:
        team_id            = validated_data["team_id"]
        challenged_team_id = validated_data["challenged_team_id"]
        pitch_id           = validated_data["pitch_id"]
        club_id            = validated_data["club_id"]
        date               = validated_data["date"]
        start_time         = validated_data["start_time"]
        end_time           = validated_data["end_time"]

        # ── Query 1: fetch both teams + active-member count in one shot ────
        teams = (
            Team.objects
            .filter(
                id__in=[team_id, challenged_team_id],
                challenge_mode=True,
                is_active=True,
            )
            .annotate(
                active_member_count=Count(
                    "teammember",
                    filter=Q(teammember__status=MemberStatus.ACTIVE),
                )
            )
            .in_bulk()          # → {uuid: Team}  —  O(1) lookups below
        )

        team            = CreateChallengeService._resolve_team(teams, team_id,            "فريقك")
        challenged_team = CreateChallengeService._resolve_team(teams, challenged_team_id, "قريق الخصم")

        # Captain guard — no DB hit, uses the already-fetched captain_id
        if team.captain_id != requesting_user_id:
            raise ValidationError({"error": "حصرًا للقائد فقط."})
        
        if team.active_member_count != challenged_team.active_member_count:
            raise ValidationError({"error": "يجب ان يكون الفريقان بنفس عدد الاعبين النشطين"})


        # ── Query 2: confirm pitch belongs to the club and both are active ──
        if not Pitch.objects.filter(
            id=pitch_id,
            club_id=club_id,
            club__is_active=True,
            is_active=True,
            is_deteted=False,          # keeping original spelling
        ).exists():
            raise ValidationError(
                {"error": "النادي أو الملعب غير موجود أو غير نشط."}
            )

        # Everything below can race; lock it all inside one transaction.

        # ── Query 3: player-level conflict check ──────────────────────
        # Build a subquery of all active player IDs across both teams.
        # Django inlines this as a SQL subquery — still ONE db round trip.
        active_players = TeamMember.objects.filter(
            team_id__in=[team_id, challenged_team_id],
            status=MemberStatus.ACTIVE,
        ).values("player_id")

        # A conflict exists if any of those players is already a member
        # of a team (challenger OR challenged side) in an overlapping challenge.
        conflict = Challenge.objects.filter(
            Q(
                team__teammember__player_id__in=active_players,
                team__teammember__status=MemberStatus.ACTIVE,
            ) |
            Q(
                challenged_team__teammember__player_id__in=active_players,
                challenged_team__teammember__status=MemberStatus.ACTIVE,
            ),
            date=date,
            status__in=[ChallengeStatus.PENDING_OWNER, ChallengeStatus.PENDING_PAY, ChallengeStatus.ACCEPTED],
            start_time__lt=end_time,
            end_time__gt=start_time,
        ).exists()

        if conflict:
            raise ValidationError(
                {"error": "لا يمكن إنشاء التحدي بسبب تعارض في جدول الحجز لأحد أعضاء الفريقين."}
            )

        # ── Query 4: pitch booking conflict ────────────────────────────
        overlapping = Booking.objects.filter(
            pitch_id=pitch_id,
            date=date,
            status__in=BOOKING_STATUS_DENIED,
            start_time__lt=end_time,
            end_time__gt=start_time,
        ).exists()

        if overlapping:
            raise ValidationError(
                {"error": "هدا الملعب غير متاح في هذا الوقت بسبب حجز موجود بالفعل."}
            )

        # ── Query 5: write ─────────────────────────────────────────────
        challenge = Challenge.objects.create(
            team_id=team_id,
            challenged_team_id=challenged_team_id,
            pitch_id=pitch_id,
            club_id=club_id,
            start_time=start_time,
            end_time=end_time,
            date=date,
        )

        print(challenge)
        return challenge



    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_team(teams_bulk: dict, team_id, label: str) -> Team:
        team = teams_bulk.get(team_id)
        if not team:
            raise ValidationError(
                {"error": f"{label} غير موجود أو غير مؤهل للتحدي."}
            )
        if team.active_member_count < settings.MIN_TEAM_MEMBERS_FOR_CHALLENGE:
            raise ValidationError(
                {"error": f"{label} يجب أن يكون لديه {settings.MIN_TEAM_MEMBERS_FOR_CHALLENGE} أعضاء نشطين على الأقل."}
            )
        return team
