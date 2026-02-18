from decimal import Decimal, ROUND_HALF_UP
from dashboard_manage.models import ClubEquipment, Equipment
from player_booking.models import BookingEquipment, Booking, BookingStatus
from django.db.models import Q, Sum, F
from datetime import date, timedelta
from rest_framework.exceptions import ValidationError
from django.core.files.storage import default_storage

class EquipmentBookingService:
    """
    Service class for managing club time schedules and pricing calculations.
    
    This service handles:
    - Fetching club opening/closing times
    - Applying pricing rules (default, weekly exceptions, specific date exceptions)
    - Calculating adjusted pitch prices based on time-based pricing multipliers
    """
   
    @classmethod
    def Create_Equipment_Booking(cls, club_id, booking:Booking , equipments):
        
        final_price = booking.price
        equipment_ids = [ equipment['id'] for equipment in equipments]
        
        equipment_quantities = (
            BookingEquipment.objects
            .filter(
                booking__club_id=club_id,
                booking__date=booking.date,
                booking__status__in=[
                BookingStatus.PENDING_PAY.value,
                BookingStatus.COMPLETED.value,
                BookingStatus.PENDING_PLAYER.value
                ],
                booking__start_time__lt=booking.end_time,
                booking__end_time__gt=booking.start_time,
                equipment_id__in = equipment_ids
            )  
            .values('equipment_id')  
            .annotate(total_booked_quantity=Sum('quantity'))  
        )

        old_booked_map = {
            item['equipment_id']: item['total_booked_quantity'] 
            for item in equipment_quantities
        }
        new_booked_map = {
            item['id']: item['quantity']
            for item in equipments
        }

        club_equipments = ClubEquipment.objects.select_for_update().values('id', 'quantity', 'price').filter(club_id=club_id, is_active=True, id__in = equipment_ids)
        if len(club_equipments) != len(equipment_ids):  
            raise ValidationError({"equipment": "equipment must be active"})

        BookingEquipment_list = list()
        for equipment in club_equipments:
            quantity = (equipment['quantity'] - old_booked_map.get(equipment['id'],0)) - new_booked_map.get(equipment['id'],0)
            if quantity < 0:
                raise ValidationError({"equipment": f"equipment not available"})

            final_equipment_price = new_booked_map.get(equipment['id'],0) * equipment['price']
            BookingEquipment_list.append(BookingEquipment(
                booking_id=booking.id,
                equipment_id=equipment['id'],
                quantity= new_booked_map.get(equipment['id'],0),
                price= final_equipment_price
            ))

            final_price = final_price + final_equipment_price 
        
        BookingEquipment.objects.bulk_create(BookingEquipment_list)

        booking.final_price=final_price
        booking.save(update_fields=['final_price'])




             
            
