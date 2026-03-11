from rest_framework.exceptions import PermissionDenied

from ..models import Challenge, ChallengeStatus
from player_team.models import Team


class GetSentChallengesService:
    """
    Returns all challenges sent BY `team_id` (i.e. team is the challenger).
    The requesting user must be the captain of that team.

    DB hits: 2
      1. Verify team exists + user is captain  (indexed PK + captain FK)
      2. Fetch matching challenges with related data via select_related
    """

    # Statuses that are still "live" — captain cares about these.
    # Adjust if you also want to show historical (REJECTED / CANCELED).
    VISIBLE_STATUSES = [
        ChallengeStatus.PENDING_TEAM,
        ChallengeStatus.PENDING_OWNER,
        ChallengeStatus.PENDING_PAY,
        ChallengeStatus.ACCEPTED,
    ]


    @staticmethod
    def execute(team_id, requesting_user_id) -> list[Challenge]:

        # ── Query 1: auth guard ────────────────────────────────────────────
        if not Team.objects.filter(
            id=team_id,
            captain_id=requesting_user_id,
            is_active=True,
        ).exists():
            raise PermissionDenied(
                "You are not the captain of this team or the team does not exist."
            )

        # ── Query 2: sent challenges ───────────────────────────────────────
        # Filter by team (sender side), select_related so the serializer
        # reads .challenged_team.name / .pitch.name etc. with zero extra hits.
        return (
            Challenge.objects
            .filter(
                team_id=team_id,
                status__in=GetSentChallengesService.VISIBLE_STATUSES,
            )
            .select_related("challenged_team", "pitch", "club","challenged_team__logo")
            .order_by("-created_at")
        )