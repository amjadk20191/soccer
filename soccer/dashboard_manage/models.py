from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.utils.translation import gettext_lazy as _
from core.models import User
from core.utils import upload_to_model_name
from .validators import validate_working_days
import uuid


class Club(models.Model):
    """Football clubs/venues"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    manager = models.OneToOneField(User, on_delete=models.CASCADE, related_name="club")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    address = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    open_time = models.TimeField()
    close_time = models.TimeField()
    working_days = models.JSONField(default=dict, validators=[validate_working_days])
    logo = models.ImageField(upload_to=upload_to_model_name, validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "webp"], message="Only JPG, JPEG, PNG, and WEBP images are allowed." )])
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    rating_count = models.PositiveBigIntegerField(default=0, validators=[MinValueValidator(0)])
    flexible_reservation = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)



    class Meta:
        db_table = 'clubs'
        verbose_name = _('Club')
        verbose_name_plural = _('Clubs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['manager']),
            models.Index(fields=['rating_avg']),
            models.Index(fields=['longitude', 'latitude']),
        ]
    
    def __str__(self):
        return self.name


class ClubPricing(models.Model):
    """Dynamic pricing for clubs"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    type = models.SmallIntegerField(choices=[
        (1, _('Weekday')),
        (2, _('date'))
    ])
    day_of_week = models.SmallIntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(7)])
    date = models.DateField(blank=True, null=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    percent = models.DecimalField(max_digits=7, decimal_places=4)
    
    class Meta:
        db_table = 'clubs_pricing'
        verbose_name = _('Club Pricing')
        verbose_name_plural = _('Club Pricings')
        indexes = [
            models.Index(fields=['club', 'day_of_week']),
            models.Index(fields=['club', 'date']),
        ]
    






class Pitch(models.Model):
    """Football pitches within clubs"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to=upload_to_model_name, validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "webp"], message="Only JPG, JPEG, PNG, and WEBP images are allowed." )])
    type = models.CharField(max_length=15)
    size_high = models.DecimalField(max_digits=5, decimal_places=2)
    size_width = models.DecimalField(max_digits=5, decimal_places=2)
    is_active = models.BooleanField(default=True)
    price_first = models.DecimalField(max_digits=10, decimal_places=2)
    price_second = models.DecimalField(max_digits=10, decimal_places=2)
    time_interval = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    
    class Meta:
        db_table = 'pitches'
        verbose_name = _('Pitch')
        verbose_name_plural = _('Pitches')
        ordering = ['club', 'name']
        indexes = [
            models.Index(fields=['club', 'is_active']),
        ]


# Reservation Type: 60 or 90 or 120
class ReservationTypeHoure(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    minutes = models.PositiveSmallIntegerField()
    class Meta:
        indexes = [
            models.Index(fields=['club']),
        ]