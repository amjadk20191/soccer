from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.utils.translation import gettext_lazy as _
from core.models import User
from core.utils import upload_to_model_name
from .validators import validate_working_days
import uuid

from django.utils import timezone



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


class ClubStaff(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.user} - {self.club}"

class ClubOpeningTimeHistory(models.Model):
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    open_time = models.TimeField()
    close_time = models.TimeField()
    created_at = models.DateField(default=timezone.localdate)

class ClubPricing(models.Model):
    """Dynamic pricing for clubs"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    type = models.SmallIntegerField(choices=[
        (1, _('Weekday')),
        (2, _('date'))
    ])
    day_of_week = models.SmallIntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(6)])
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
    

class PitchTypes(models.IntegerChoices):
    Natural_grass = 1, _('عشب طبيعي')
    Industrial_grass = 2, _('عشب صناعي')
    Ground = 3, _('زفت')
    earthy = 4, _('أرضي')
    




class Pitch(models.Model):
    """Football pitches within clubs"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to=upload_to_model_name, validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "webp"], message="Only JPG, JPEG, PNG, and WEBP images are allowed." )])
    type = models.CharField(max_length=15)
    size_high = models.DecimalField(max_digits=5, decimal_places=2,  validators=[MinValueValidator(1.0)])
    size_width = models.DecimalField(max_digits=5, decimal_places=2,  validators=[MinValueValidator(1.0)])
    is_active = models.BooleanField(default=True)
    is_deteted = models.BooleanField(default=False)
    price_first = models.DecimalField(max_digits=10, decimal_places=2,  validators=[MinValueValidator(1.0)])
    price_second = models.DecimalField(max_digits=10, decimal_places=2,  validators=[MinValueValidator(1.0)])
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




class Equipment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=300, blank=True)
    image = models.ImageField(upload_to=upload_to_model_name, validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "webp"], message="Only JPG, JPEG, PNG, and WEBP images are allowed." )])




class ClubEquipment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE)
    quantity = models.PositiveSmallIntegerField(validators=[MinValueValidator(0)])
    price = models.DecimalField(max_digits=10, decimal_places=2,  validators=[MinValueValidator(1.0)])
    is_active = models.BooleanField(default=True)
    is_deteted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["club", "equipment"],
                condition=models.Q(is_deteted=False),
                name="uniq_club_equipment"
            )
        ]




class BookingPriceStatistics(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    day = models.DateField()
    money_from_completed_owner = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    money_from_completed_player = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    money_from_pending_pay_player = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    money_from_pending_pay_owner = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    
    class Meta:
        unique_together = ("club", "day")

class BookingNumStatistics(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    day = models.DateField()
    
    completed_num = models.PositiveSmallIntegerField(default=0)
    completed_num_owner = models.PositiveSmallIntegerField(default=0)
    canceled_num_from_completed_owner = models.PositiveSmallIntegerField(default=0)
    canceled_num_from_pending_pay_owner = models.PositiveSmallIntegerField(default=0)
    canceled_num_from_pending_pay_player = models.PositiveSmallIntegerField(default=0)
    canceled_num_from_completed_player = models.PositiveSmallIntegerField(default=0)
    reject_num = models.PositiveSmallIntegerField(default=0)
    pending_pay_num = models.PositiveSmallIntegerField(default=0)
    pending_pay_num_owner = models.PositiveSmallIntegerField(default=0)
    pending_player_num = models.PositiveSmallIntegerField(default=0)
    no_Show_num = models.PositiveSmallIntegerField(default=0)
    disputed_num = models.PositiveSmallIntegerField(default=0)
    expired_num = models.PositiveSmallIntegerField(default=0)

  
    class Meta:
        unique_together = ("club", "day")

class ClubHourlyStatistics(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE)
    date = models.DateField()
    hour = models.SmallIntegerField()  # 0 to 23
    booked_minutes = models.IntegerField(default=0) # should be at max 60 

    class Meta:
        unique_together = ("club", "pitch", "date", "hour") 


class ClubEquipmentStatistics(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    club_equipment = models.ForeignKey(ClubEquipment, on_delete=models.CASCADE)
    date = models.DateField()
    quantity_by_ower = models.PositiveSmallIntegerField(default=0) # for booking done by owner
    revenue_by_owner = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))# for booking done by owner
    quantity_by_player = models.PositiveSmallIntegerField(default=0)# for booking done by player
    revenue_by_player = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))# for booking done by player

    class Meta:
        unique_together = ("club", "club_equipment", "date") 





class BookingDuration (models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    duration = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])