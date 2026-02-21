from django.db import transaction, IntegrityError
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from ..models import ClubEquipment, Club, Equipment


class EquipmentManageService:

    
    @classmethod
    def create_equipment(cls, equipment_id, club_id, quantity):
        if quantity is None or int(quantity) < 0:
            raise ValidationError({"quantity": "Quantity must be >= 0"})

        club_exists = Club.objects.filter(id=club_id).exists()
        if not club_exists:
            raise ValidationError({"club_id": "Club not found"})

        equipment_exists = Equipment.objects.filter(id=equipment_id).exists()
        if not equipment_exists:
            raise ValidationError({"equipment_id": "Equipment not found"})

        try:
            with transaction.atomic():
                obj = ClubEquipment.objects.create(
                    club_id=club_id,
                    equipment_id=equipment_id,
                    quantity=int(quantity),
                    is_active=True,
                    is_deteted=False
                )
                return obj

        except IntegrityError:
            raise ValidationError({
                "detail": "This equipment already exists for this club."
            })