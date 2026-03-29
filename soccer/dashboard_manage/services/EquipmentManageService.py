from django.db import transaction, IntegrityError
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from ..models import ClubEquipment, Club, Equipment


class EquipmentManageService:

    
    @classmethod
    def create_equipment(cls, equipment_id, club_id, quantity, price):
        if quantity is None or int(quantity) < 0:
            raise ValidationError({"quantity": "الكمية يجب أن تكون اكبر من 0"})

        club_exists = Club.objects.filter(id=club_id).exists()
        if not club_exists:
            raise ValidationError({"error": "النادي غير موجود."})

        equipment_exists = Equipment.objects.filter(id=equipment_id).exists()
        if not equipment_exists:
            raise ValidationError({"error": "العدة غير موجودة."})

        try:
            exists = ClubEquipment.objects.filter(
                club_id=club_id,
                equipment_id=equipment_id,
                is_deteted=False
            ).exists()

            if exists:
                raise ValidationError({
                    "error": "هذه المعدّات موجودة بالفعل لهذا النادي."
                })
            return ClubEquipment.objects.create(
                club_id=club_id,
                equipment_id=equipment_id,
                quantity=int(quantity),
                price=price,
                is_active=True,
                is_deteted=False
            )

        except IntegrityError:
            raise ValidationError({
                "error": "هذه المعدّات موجودة بالفعل لهذا النادي."
            })