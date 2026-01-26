from django.db import models
from django.utils.translation import gettext_lazy as _
from player_booking.models import Booking, BookingStatus
from core.models import User
from dashboard_manage.models import Club
import uuid


class BookingStatusHistory(models.Model):
    """Track booking status changes"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE)
    status = models.PositiveSmallIntegerField(choices=BookingStatus.choices)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    change_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'booking_status_history'
        verbose_name = _('Booking Status History')
        verbose_name_plural = _('Booking Status Histories')
        ordering = ['-change_at']
    



class BookingNotification(models.Model):
    """Notifications for booking updates"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE)
    send_by = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='sended_booking_notifications')
    send_to = models.ForeignKey(User, on_delete=models.CASCADE)
    old_date = models.DateField()
    old_start_time = models.TimeField()
    old_end_time = models.TimeField()
    new_date = models.DateField()
    new_start_time = models.TimeField()
    new_end_time = models.TimeField()
    status = models.SmallIntegerField(choices=[
        (1, _('Pending')),
        (2, _('accept')),
        (3, _('reject'))
        ], default=1)
    
    
    class Meta:
        db_table = 'booking_notifications'
        verbose_name = _('Booking Notification')
        verbose_name_plural = _('Booking Notifications')
        ordering = ['-id']
        indexes = [
            models.Index(fields=['send_to']),
        ]

