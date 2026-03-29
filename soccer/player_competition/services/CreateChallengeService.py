from django.db import transaction
from django.db.models import Count, Q
from soccer.enm import BOOKING_STATUS_DENIED
from django.conf import settings

from ..models import Challenge, ChallengeStatus
from player_team.models import Team, TeamMember, MemberStatus
from player_booking.models import Booking
from dashboard_manage.models import Pitch
from rest_framework.exceptions import ValidationError


class CreateChallengeService:

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

        team            = CreateChallengeService._resolve_team(teams, team_id,            "Your team")
        challenged_team = CreateChallengeService._resolve_team(teams, challenged_team_id, "Challenged team")

        # Captain guard — no DB hit, uses the already-fetched captain_id
        if team.captain_id != requesting_user_id:
            raise ValidationError({"error": "حصرًا للقائد فقط."})

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
        with transaction.atomic():

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
                status__in=[ChallengeStatus.PENDING_PAY, ChallengeStatus.ACCEPTED],
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
            return Challenge.objects.create(
                team_id=team_id,
                challenged_team_id=challenged_team_id,
                pitch_id=pitch_id,
                club_id=club_id,
                start_time=start_time,
                end_time=end_time,
                date=date,
            )

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_team(teams_bulk: dict, team_id, label: str) -> Team:
        team = teams_bulk.get(team_id)
        if not team:
            raise ValidationError(
                {"error": f"{label} غير موجود أو غير مؤهل للتحدي."}
            )
        if team.active_member_count < settings.MIN_TEAM_MEMBERS:
            raise ValidationError(
                {"error": f"{label} يجب أن يكون لديه {settings.MIN_TEAM_MEMBERS} أعضاء نشطين على الأقل."}
            )
        return team
