from django.db import transaction
from dashboard_booking.models import  BookingNotification
from  player_booking.models import Booking, BookingStatus
from dashboard_manage.models import Pitch
from rest_framework.exceptions import ValidationError 
from django.shortcuts import get_object_or_404

class BookingService:
    
    
    @classmethod
    @transaction.atomic
    def owner_update_booking_status(cls, booking_id, status, club_id):
        booking = get_object_or_404(
            Booking.objects.select_for_update(), pk=booking_id, pitch__club_id=club_id
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
                raise ValidationError("The status not valid")

    @classmethod
    def convert_to_pending_pay(cls, booking):
        """Convert Pending_manager to Pending_pay"""
        if booking.status != BookingStatus.PENDING_MANAGER:
            raise  ValidationError("Only bookings with Pending_manager status can be converted to Pending_pay")
        
        booking.status = BookingStatus.PENDING_PAY
        booking.save(update_fields=['status', 'updated_at'])
        return booking
    
  
    @classmethod
    def reject_booking(cls, booking):
        """Reject booking (from Pending_manager)"""
        if booking.status != BookingStatus.PENDING_MANAGER:
            raise ValidationError("Only bookings with Pending_manager status can be rejected")
        
        booking.status = BookingStatus.REJECT
        booking.save(update_fields=['status', 'updated_at'])
        return booking

    @classmethod
    def disputed_booking(cls, booking):
        """disputed booking (from Completed or Pending_pay)"""
        if not(booking.status == BookingStatus.COMPLETED or (booking.by_owner and booking.status == BookingStatus.PENDING_PAY)):
            raise ValidationError("Only bookings with Completed or Pending_pay (created by owner) status can be rejected")
        
        booking.status = BookingStatus.DISPUTED
        booking.save(update_fields=['status', 'updated_at'])
        return booking


    @classmethod
    def no_show_booking(cls, booking):
        """no_show booking (from Completed or Pending_pay)"""
        if not(booking.by_owner and booking.status == BookingStatus.PENDING_PAY):
            raise ValidationError("Only bookings with Completed or Pending_pay status can be rejected")
        
        booking.status = BookingStatus.NO_SHOW
        booking.save(update_fields=['status', 'updated_at'])
        return booking
    
    @classmethod
    def owner_canceled_booking(cls, booking):
        """CANCELED booking (from Completed or Pending_pay) by owner"""
        if not(booking.status == BookingStatus.COMPLETED or (booking.by_owner and booking.status == BookingStatus.PENDING_PAY)):
            raise ValidationError("Only bookings with Completed or Pending_pay (created by owner) or PENDING_PLAYER status can be rejected")
        
        booking.status = BookingStatus.CANCELED
        booking.save(update_fields=['status', 'updated_at'])
        return booking
    
    @classmethod
    def owner_completed_booking(cls, booking):
        """Completed booking (from Pending_pay) by owner"""
        if not(booking.by_owner and booking.status == BookingStatus.PENDING_PAY):
            raise ValidationError("Only bookings with Completed or Pending_pay (created by owner) status can be rejected")
        
        has_overlap = Booking.objects.filter(
            pitch=booking.pitch,
            date=booking.date,
            status=BookingStatus.COMPLETED,  
            start_time__lt=booking.end_time,
            end_time__gt=booking.start_time
        ).exclude(pk=booking.pk).exists() 
        
        if has_overlap:
            raise ValidationError("Cannot complete this booking: It overlaps with another confirmed booking.")

        booking.status = BookingStatus.COMPLETED
        booking.save(update_fields=['status', 'updated_at'])
        return booking
    
    
    @classmethod
    @transaction.atomic
    def convert_to_pending_player(cls, booking, club_id, new_date, new_start_time, new_end_time):
        """Convert Pending_manager to Pending_player and create notification"""
        if booking.status != BookingStatus.PENDING_MANAGER:
            raise ValidationError("Only bookings with Pending_manager status can be converted to Pending_player")
        
        if not booking.player:
            raise ValidationError("Cannot send notification: booking has no player assigned")
        
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
  
    ################################## Player
    @classmethod
    @transaction.atomic
    def player_canceled_booking(cls, booking):
        """CANCELED booking (from Completed or Pending_pay) by player"""
        if not(booking.status in [BookingStatus.COMPLETED, BookingStatus.PENDING_PAY]):
            raise ValidationError("Only bookings with Completed or Pending_pay (created by player) status can be rejected")
        
        booking.status = BookingStatus.CANCELED
        booking.save(update_fields=['status', 'updated_at'])
        return booking