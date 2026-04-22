
from rest_framework.exceptions import ValidationError

from dashboard_manage.models import ClubEquipment
from player_competition.models import ChallengeEquipment, Challenge


class ChallengeEquipmentService:

    @staticmethod
    def create_challenge_equipments(challenge: Challenge, equipments: list[dict]) -> None:
        """
        Validates all equipment IDs belong to the challenge's club,
        then bulk inserts into ChallengeEquipment.
        """
        equipment_ids = [item['id'] for item in equipments]

        # Single query — fetch only what belongs to this club
        existing = (
            ClubEquipment.objects
            .filter(id__in=equipment_ids, club_id=challenge.club_id)
            .values_list('id', flat=True)
        )
        existing_ids = set(str(pk) for pk in existing)

        # Validate all requested IDs are valid for this club
        invalid_ids = [str(eid) for eid in equipment_ids if str(eid) not in existing_ids]
        if invalid_ids:
            raise ValidationError({
                "equipments": f"المعدات التالية غير موجودة أو لا تنتمي لهذا النادي: {', '.join(invalid_ids)}"
            })

        ChallengeEquipment.objects.bulk_create([
            ChallengeEquipment(
                challenge=challenge,
                equipment_id=item['id'],
                quantity=item['quantity'],
            )
            for item in equipments
        ])




