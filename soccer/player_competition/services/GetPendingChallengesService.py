from rest_framework.exceptions import PermissionDenied

from ..models import Challenge, ChallengeStatus
from player_team.models import Team


class GetPendingChallengesService:
    """
    Returns all PENDING_TEAM challenges received by `team_id`.
    The requesting user must be the captain of that team.

    DB hits: 2
      1. Verify team exists + user is captain  (indexed PK + captain FK)
      2. Fetch matching challenges with related data via select_related
    """

    @staticmethod
    def execute(team_id, requesting_user_id) -> list[Challenge]:

        # ── Query 1: auth guard ────────────────────────────────────────────
        if not Team.objects.filter(id=team_id, captain_id=requesting_user_id, is_active=True).exists():
            raise PermissionDenied(detail={"error": "أنت لست قائد هذا الفريق أو الفريق غير موجود."})

        # ── Query 2: challenges ────────────────────────────────────────────
        # select_related pulls team / pitch / club in the same JOIN —
        # serializer reads .team.name etc. with zero extra queries.
        return (
            Challenge.objects
            .filter(
                challenged_team_id=team_id,
                status=ChallengeStatus.PENDING_TEAM,
            )
            .select_related("team", "pitch", "club", "team__logo")
            .order_by("-created_at")
        )