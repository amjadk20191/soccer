from django.db import transaction
from dashboard_booking.models import  BookingNotification
from  player_booking.models import Booking, BookingStatus
from dashboard_manage.models import Pitch

class BookingService:
    """Business logic for booking operations"""
    
    @staticmethod
    @transaction.atomic
    def convert_to_pending_pay(booking):
        """Convert Pending_manager to Pending_pay"""
        if booking.status != BookingStatus.PENDING_MANAGER:
            raise ValueError("Only bookings with Pending_manager status can be converted to Pending_pay")
        
        booking.status = BookingStatus.PENDING_PAY
        booking.save(update_fields=['status', 'updated_at'])
        return booking
    
    @staticmethod
    @transaction.atomic
    def convert_to_pending_player(booking, club, new_date, new_start_time, new_end_time):
        """Convert Pending_manager to Pending_player and create notification"""
        if booking.status != BookingStatus.PENDING_MANAGER:
            raise ValueError("Only bookings with Pending_manager status can be converted to Pending_player")
        
        if not booking.player:
            raise ValueError("Cannot send notification: booking has no player assigned")
        
        # Create notification
        BookingNotification.objects.create(
            booking=booking,
            send_by=club,
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
    
    @staticmethod
    @transaction.atomic
    def reject_booking(booking):
        """Reject booking (from Pending_manager or Pending_player)"""
        if booking.status not in [BookingStatus.PENDING_MANAGER, BookingStatus.PENDING_PLAYER]:
            raise ValueError("Only bookings with Pending_manager or Pending_player status can be rejected")
        
        booking.status = BookingStatus.REJECT
        booking.save(update_fields=['status', 'updated_at'])
        return booking