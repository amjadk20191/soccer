from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError

from ..models import Challenge, ChallengeStatus


class CancelChallengeService:
    """
    Allows the captain of the *sending* team to cancel a challenge they issued.

    Rules:
      - Only the captain of `challenge.team` can cancel.
      - Only challenges still in a cancelable state can be cancelled.
      - Once ACCEPTED or beyond (PENDING_PAY etc.), cancellation is blocked.

    DB hits: 2
      1. Single fetch — existence + ownership check in one query
      2. Targeted UPDATE (no full model save)
    """

    CANCELABLE_STATUSES = [
        ChallengeStatus.PENDING_TEAM,    # other team hasn't replied yet
        ChallengeStatus.PENDING_OWNER,   # waiting for club owner approval
    ]

    @staticmethod
    def execute(challenge_id, requesting_user_id) -> Challenge:

        # ── Query 1: fetch + auth + status in one shot ─────────────────────
        # Filtering on team__captain_id means the DB enforces ownership —
        # no separate permission query needed.
        challenge = (
            Challenge.objects
            .filter(
                id=challenge_id,
                team__captain_id=requesting_user_id,   # only sender's captain
            ).values('status', 'id')
            .first()
        )

        if challenge is None:
            # Same 404 for "not found" and "not your challenge" — avoids leaking.
            raise NotFound("Challenge not found or you are not authorised to cancel it.")

        if challenge['status'] not in CancelChallengeService.CANCELABLE_STATUSES:
            raise ValidationError(
                f"This challenge cannot be cancelled in its current state "
            )

        # ── Query 2: targeted UPDATE — no full model save ──────────────────
        Challenge.objects.filter(id=challenge['id'],  team__captain_id=requesting_user_id).update(
            status=ChallengeStatus.CANCELED,
        )

        return 'done'