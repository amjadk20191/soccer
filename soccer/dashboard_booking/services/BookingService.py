from django.db import IntegrityError, transaction
from dashboard_booking.models import  BookingNotification
from  player_booking.models import Booking, BookingStatus, BookingEquipment
from dashboard_manage.models import Pitch, ClubEquipment 
from rest_framework.exceptions import ValidationError 
from django.shortcuts import get_object_or_404
from soccer.enm import BOOKING_STATUS_DENIED
from django.db.models import Prefetch

from player_competition.models import Challenge, ChallengePlayerBooking, ChallengeStatus
from player_team.models import MemberStatus, TeamMember
from .EquipmentBookingService import EquipmentBookingService

class BookingService:
    
    
    @classmethod
    @transaction.atomic
    def owner_update_booking_status(cls, booking_id, status, club_id):
        booking = get_object_or_404(
            Booking.objects.select_for_update(), pk=booking_id, club_id=club_id
            )
                
        match status:
            case BookingStatus.PENDING_PAY.value:
                cls.convert_to_pending_pay(booking)
            case BookingStatus.REJECT.value:
                cls.reject_booking(booking)
            case BookingStatus.DISPUTED.value:
                cls.disputed_booking(booking)
            case BookingStatus.NO_SHOW.value:
                cls.no_show_booking(booking)
            case BookingStatus.CANCELED.value:
                cls.owner_canceled_booking(booking)
            case BookingStatus.COMPLETED.value:
                cls.owner_completed_booking(booking)
            case _:
                raise ValidationError({"error": "الحالة غير صحيحة"})

    @classmethod
    @transaction.atomic
    def convert_to_pending_pay(cls, booking):
        """Convert Pending_manager to Pending_pay"""
        if booking.status != BookingStatus.PENDING_MANAGER:
            raise  ValidationError({"error": "فقط الحجوزات التي في حالة معلقة (من قبل المدير) يمكن تحويلها إلى معلقة بانتظار الدفع "})
        cls._check_if_has_overlap_booking(booking)

        print("//////////////////////////////////////////////////////////////////")
        print(booking.is_challenge)
        if booking.is_challenge:
            challenge = (
                Challenge.objects
                .filter(booking_id=booking.id)
                .only('id', 'team_id', 'challenged_team_id')
                .first()
            )
            print(challenge)
            print("//////////////////////////////////////////////////////////////////")

            if challenge:
                Challenge.objects.filter(id=challenge.id).update(status=ChallengeStatus.PENDING_PAY)
                cls._seed_challenge_player_bookings(booking, challenge)

        booking.status = BookingStatus.PENDING_PAY
        booking.save(update_fields=['status', 'updated_at'])
        return booking
    
    @classmethod
    @transaction.atomic
    def reject_booking(cls, booking):
        """Reject booking (from Pending_manager)"""
        if booking.status != BookingStatus.PENDING_MANAGER:
            raise ValidationError({"error": "فقط الحجوزات التي في حالة معلقة (من قبل المدير) يمكن إلغاؤها"})
        if booking.is_challenge:
            Challenge.objects.filter(booking_id=booking.id).update(
                status=ChallengeStatus.REJECTED)


        booking.status = BookingStatus.REJECT
        booking.save(update_fields=['status', 'updated_at'])
        return booking

    @classmethod
    @transaction.atomic
    def disputed_booking(cls, booking):
        """disputed booking (from Completed or Pending_pay)"""
        if not(
            # booking.status == BookingStatus.COMPLETED or 
            (booking.by_owner and booking.status == BookingStatus.PENDING_PAY)):
            raise ValidationError({"error": "فقط الحجوزات التي في حالة مكتملة أو في انتظار الدفع (تم انشاءها من قبل صاحب الملعب) يمكن إلغاؤها"})
        
        booking.status = BookingStatus.DISPUTED
        booking.save(update_fields=['status', 'updated_at'])
        return booking

    @classmethod
    @transaction.atomic
    def no_show_booking(cls, booking):
        """no_show booking (from Completed or Pending_pay)"""
        if not(booking.by_owner and booking.status == BookingStatus.PENDING_PAY):
            raise ValidationError({"error": "فقط الحجوزات التي في حالة مكتملة أو في انتظار الدفع  يمكن إلغاؤها"})
        
        booking.status = BookingStatus.NO_SHOW
        booking.save(update_fields=['status', 'updated_at'])
        return booking
    
    @classmethod
    @transaction.atomic
    def owner_canceled_booking(cls, booking):
        """CANCELED booking (from Completed or Pending_pay) by owner"""
        if not(booking.status == BookingStatus.CLOSED or booking.status == BookingStatus.COMPLETED or (booking.by_owner and booking.status == BookingStatus.PENDING_PAY)):
            raise ValidationError({"error": "فقط الحجوزات التي في حالة مكتملة أو في انتظار الدفع (تم انشاءها من قبل صاحب الملعب) او بانتظار اللاعب يمكن إلغاؤها"})
        
        if booking.is_challenge:
            Challenge.objects.filter(booking_id=booking.id).update(
                status=ChallengeStatus.CANCELED)

        booking.status = BookingStatus.CANCELED
        booking.save(update_fields=['status', 'updated_at'])
        return booking
    
    @classmethod
    @transaction.atomic
    def owner_completed_booking(cls, booking):
        """Completed booking (from Pending_pay) by owner"""
        if not(booking.by_owner and booking.status == BookingStatus.PENDING_PAY):
            raise ValidationError({"error": "فقط الحجوزات التي في حالة مكتملة أو في انتظار الدفع (تم انشاءها من قبل صاحب الملعب) يمكن إلغاؤها"})

        booking.status = BookingStatus.COMPLETED
        booking.save(update_fields=['status', 'updated_at'])
        return booking
    
    @classmethod
    @transaction.atomic
    def convert_to_pending_player(cls, booking, club_id, new_date, new_start_time, new_end_time):
        """Convert Pending_manager to Pending_player and create notification"""
        if booking.status != BookingStatus.PENDING_MANAGER and booking.is_challenge:
            raise ValidationError({"error": "فقط الحجوزات التي في حالة معلقة (من قبل المدير) يمكن تحويلها إلى معلقة (من قبل اللاعب)"})
        
        if not booking.player:
            raise ValidationError({"error": "لا يمكن ارسال اشعار لهذا الحجز بسبب عدم وجود لاعب مرتبط به."})
        
        cls._check_if_has_overlap_booking(booking)
        
        # Create notification
        BookingNotification.objects.create(
            booking=booking,
            send_by_id=club_id,
            send_to=booking.player,
            old_date=booking.date,
            old_start_time=booking.start_time,
            old_end_time=booking.end_time,
            new_date=new_date,
            new_start_time=new_start_time,
            new_end_time=new_end_time
        )
        
        # Update booking status
        booking.status = BookingStatus.PENDING_PLAYER
        booking.save(update_fields=['status', 'updated_at'])
        return booking
  
    @classmethod
    def _check_if_has_overlap_booking(cls, booking:Booking):
        
        has_overlap = Booking.objects.select_for_update().filter(
            pitch=booking.pitch,
            date=booking.date,
            status__in=BOOKING_STATUS_DENIED,
            start_time__lt=booking.end_time,
            end_time__gt=booking.start_time
        ).exclude(pk=booking.pk).exists() 
        
        if has_overlap:
            raise ValidationError({"error": "لا يمكن تأكيد هذا الحجز بسبب وجود حجز آخر يتداخل مع نفس الملعب في نفس الوقت."})
        
        equipments=BookingEquipment.objects.values('equipment_id','quantity').filter(booking_id=booking.id)
        if equipments:
            equipment_ids = [ equipment['equipment_id'] for equipment in equipments]

            
            equipment_quantities = EquipmentBookingService.Get_booking_equipment_quantities(booking.club_id, booking.date, booking.start_time, booking.end_time, equipment_ids)

            old_booked_map = {
                item['equipment_id']: item['total_booked_quantity'] 
                for item in equipment_quantities
            }
            new_booked_map = {
                item['equipment_id']: item['quantity']
                for item in equipments
            }

            print("new_booked_map")
            print(new_booked_map)
            print("equipment_quantities")
            print(equipment_quantities)
            club_equipments = ClubEquipment.objects.select_for_update().values('id', 'quantity', 'price', 'equipment_id').filter(club_id=booking.club_id, is_active=True, id__in=equipment_ids, is_deteted=False)
            print(club_equipments)
            print(":::::::::::::::::::::::::::::::::")
            print(equipment_ids)
            if len(club_equipments) != len(equipment_ids):  
                raise ValidationError({"error": "العدة يجب أن تكون نشطة."})

            for equipment in club_equipments:
                print(equipment['quantity'])
                print(old_booked_map.get(equipment['id'],0))
                print(new_booked_map.get(equipment['id'],0))
                quantity = (equipment['quantity'] - old_booked_map.get(equipment['id'],0)) - new_booked_map.get(equipment['id'],0)
                if quantity < 0:
                    raise ValidationError({
                                        "error": f"الكمية المطلوبة غير متوفرة.",
                                        "id": equipment["id"],
                                        })

    @classmethod
    def _seed_challenge_player_bookings(cls, booking, challenge):
        """Bulk-insert active players from both challenge teams into ChallengePlayerBooking."""
        active_members = (
            TeamMember.objects
            .filter(
                team_id__in=[challenge.team_id, challenge.challenged_team_id],
                status=MemberStatus.ACTIVE,
            )
            .values_list('player_id', 'team_id')  # fetch both in one query
        )

        try:
            ChallengePlayerBooking.objects.bulk_create(
                [
                    ChallengePlayerBooking(
                        booking_id=booking.id,
                        challenge_id=challenge.id,
                        player_id=player_id,
                        team_id=team_id,
                    )
                    for player_id, team_id in active_members
                ],
            )
        except IntegrityError:
            raise ValidationError({
                "error": "لاعبون مسجلون مسبقاً في هذه المباراة"
            })
        
        
    ################################## Player
    @classmethod
    @transaction.atomic
    def player_canceled_booking(cls, booking):
        """CANCELED booking (from Completed or Pending_pay) by player"""
        if not(booking.status in [BookingStatus.COMPLETED, BookingStatus.PENDING_PAY]):
            raise ValidationError({"error": "فقط الحجوزات التي في حالة مكتملة أو في انتظار الدفع (من قبل اللاعب) يمكن إلغاؤها"})

        if booking.is_challenge:
            Challenge.objects.filter(booking_id=booking.id).update(
                status=ChallengeStatus.CANCELED)

        booking.status = BookingStatus.CANCELED
        booking.save(update_fields=['status', 'updated_at'])
        return booking