from decimal import Decimal, ROUND_HALF_UP
from dashboard_manage.models import ClubEquipment, Equipment
from player_booking.models import BookingEquipment, Booking, BookingStatus
from django.db.models import Q, Sum, F
from datetime import date, timedelta
from rest_framework.exceptions import ValidationError
from django.core.files.storage import default_storage
from soccer.enm import BOOKING_STATUS_DENIED
from django.db.models import F
from django.conf import settings
from django.db import transaction
from datetime import datetime, date


class EquipmentBookingService:


    @classmethod
    @transaction.atomic
    def Create_Equipment_Booking(cls, club_id, booking:Booking, equipments, start_time, end_time):
        
        final_price = booking.price
        equipment_ids = [ equipment['id'] for equipment in equipments]
        
        equipment_quantities = cls.Get_booking_equipment_quantities(club_id, booking.date, booking.start_time, booking.end_time, equipment_ids)
        print(equipment_quantities)
        print("equipment_quantities")
        old_booked_map = {
            item['equipment_id']: item['total_booked_quantity'] 
            for item in equipment_quantities
        }
        start_dt = datetime.combine(date.today(), start_time)
        end_dt = datetime.combine(date.today(), end_time)

        # Handle overnight case (e.g., 11 PM to 1 AM)
        if end_dt < start_dt:
            end_dt += timedelta(days=1)

        # Get difference in hours as a float
        time = (end_dt - start_dt).total_seconds() / 3600
        
        new_booked_map = {
            item['id']: item['quantity']
            for item in equipments
        }

        club_equipments = ClubEquipment.objects.select_for_update().values('id', 'quantity', 'price', 'equipment_id').filter(club_id=club_id, is_active=True, id__in=equipment_ids, is_deteted=False)
        print(club_equipments)
        print(":::::::::::::::::::::::::::::::::")
        print(equipment_ids)
        if len(club_equipments) != len(equipment_ids):  
            raise ValidationError({"equipment": "equipment must be active"})

        BookingEquipment_list = list()
        for equipment in club_equipments:
            quantity = (equipment['quantity'] - old_booked_map.get(equipment['id'],0)) - new_booked_map.get(equipment['id'],0)
            if quantity < 0:
                raise ValidationError({
                                    "equipment": f"equipment not available",
                                    "id": equipment["id"],
                                    })

            final_equipment_price = new_booked_map.get(equipment['id'],0) * equipment['price']* Decimal(str(time))
            BookingEquipment_list.append(BookingEquipment(
                booking_id=booking.id,
                equipment_id=equipment['id'],
                equipment_def_id=equipment['equipment_id'],
                quantity= new_booked_map.get(equipment['id'],0),
                price= final_equipment_price
            ))

            final_price = final_price + final_equipment_price

        equipments=BookingEquipment.objects.bulk_create(BookingEquipment_list)

        booking.final_price=final_price
        booking._force_signals_update = booking.status==BookingStatus.COMPLETED
        booking.save(update_fields=['final_price', 'updated_at'])

        return equipments
    
    @classmethod
    def Get_Equipment_Price(cls, club_id, equipments, start_time, end_time):
        
        final_price = 0
        equipment_ids = [ equipment['id'] for equipment in equipments]

        new_booked_map = {
            str(item['id']): item['quantity']
            for item in equipments
        }

        club_equipments = ClubEquipment.objects.values('id', 'quantity', 'price').filter(club_id=club_id, is_active=True, id__in = equipment_ids, is_deteted=False)
        if len(club_equipments) != len(equipment_ids):  
            raise ValidationError({"equipment": "equipment must be active"})
        start_dt = datetime.combine(date.today(), start_time)
        end_dt = datetime.combine(date.today(), end_time)

        # Handle overnight case (e.g., 11 PM to 1 AM)
        if end_dt < start_dt:
            end_dt += timedelta(days=1)

        # Get difference in hours as a float
        time = (end_dt - start_dt).total_seconds() / 3600

        for equipment in club_equipments:
            final_equipment_price = new_booked_map.get(str(equipment['id']),0) * equipment['price'] 
            new_booked_map[str(equipment['id'])] = final_equipment_price * Decimal(str(time))
            final_price = final_price + final_equipment_price

        new_booked_map['equipments_price'] = final_price * Decimal(str(time))
        

        return new_booked_map

            
    @classmethod
    def Get_equipment_quantities_for_time(cls, club_id, booking_date, end_time, start_time, request):
        club_equipments = (
            ClubEquipment.objects
            .select_related('equipment')
            .filter(club_id=club_id, is_active=True, is_deteted=False)
            .values('id', 'quantity', 'price', name=F('equipment__name'), description=F('equipment__description'), image=F('equipment__image'))
        )
        if not club_equipments:
            return []
       
        equipment_quantities = cls.Get_booking_equipment_quantities(club_id, booking_date, start_time, end_time)
        old_booked_map = {
            item['equipment_id']: item['total_booked_quantity'] 
            for item in equipment_quantities
        }


        for equipment in club_equipments:
            equipment['quantity'] = max(equipment['quantity'] - old_booked_map.get(equipment['id'],0), 0) 
           
           
            equipment['image'] = request.build_absolute_uri(default_storage.url(equipment['image']))
            print(equipment)
        
        return club_equipments

    @classmethod
    def Get_booking_equipment_quantities(cls, club_id, booking_date, start_time, end_time, equipment_ids=None):

        queryset = BookingEquipment.objects.select_related('booking').filter(
                booking__club_id=club_id,
                booking__date=booking_date,
                booking__status__in=BOOKING_STATUS_DENIED,
                booking__start_time__lt=end_time,
                booking__end_time__gt=start_time
            )
        
        print(queryset)
        # Apply equipment filter if provided
        if equipment_ids:
            queryset = queryset.filter(equipment_id__in=equipment_ids)
        
        # Execute query with values and annotation - RETURNS LIST OF DICTS
        equipment_quantities = queryset.values('equipment_id').annotate(total_booked_quantity=Sum('quantity'))
        
        print("equipment_quantities")
        print(equipment_quantities)
        print("equipment_quantities")
        
        return list(equipment_quantities)


