from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from core.models import User
from dashboard_manage.models import Pitch
from dashboard_manage.models import Club
import uuid


class BookingStatus(models.IntegerChoices):
    PENDING_MANAGER = 1, _('Pending_manager')
    PENDING_PLAYER = 2, _('Pending_player')
    PENDING_PAY = 3, _('Pending_pay')
    COMPLETED = 4, _('Completed')
    CANCELED = 5, _('Canceled')
    REJECT = 6, _('reject')



class Booking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE)
    player = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.PositiveSmallIntegerField(choices=BookingStatus.choices, default=BookingStatus.PENDING_MANAGER)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    note_admin = models.TextField(blank=True)
    
    class Meta:
        db_table = 'bookings'
        verbose_name = _('Booking')
        verbose_name_plural = _('Bookings')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['pitch', 'date']),
            models.Index(fields=['pitch', 'date','start_time']),
            models.Index(fields=['player']),
            models.Index(fields=['status']),
        ]



class Review(models.Model):
    """Reviews for bookings"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE)
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'reviews'
        verbose_name = _('Review')
        verbose_name_plural = _('Reviews')
        indexes = [
            models.Index(fields=['club']),
            models.Index(fields=['booking']),
        ]

