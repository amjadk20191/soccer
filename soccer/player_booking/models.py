from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from core.models import User
from dashboard_manage.models import Pitch, ClubEquipment, Equipment
from dashboard_manage.models import Club
import uuid
from decimal import Decimal

from django.utils import timezone


class BookingStatus(models.IntegerChoices):
    PENDING_MANAGER = 1, _('بانتظار تاكيد المدير')
    PENDING_PLAYER = 2, _('بانتظار تاكيد اللاعب')
    PENDING_PAY = 3, _('بانتظار الدفع')
    COMPLETED = 4, _('مكتمل')
    CANCELED = 5, _('ملغى')
    REJECT = 6, _('مرفوض')
    NO_SHOW = 7, _('لم يحضر')
    DISPUTED = 8, _('مشكلة')
    EXPIRED = 9, _('انتهت صلاحيته')
    CLOSED = 10, _('فترة مغلقة')

class PayStatus(models.IntegerChoices):
    LATER = 1, _('لاحقا')
    DEPOSIT = 2, _('دفعة مقدمة')
    ONLINE = 3, _('اونلاين')
    CASH = 4, _('نقدا')
    UNKNOWN = 5, _('غير معروف')

class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]
    
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    # None = unlimited usage, any number = max times it can be used total
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)

    club = models.ForeignKey(
        'dashboard_manage.Club',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='coupons'
    )


    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False
        return True

    def apply_discount(self, price):
        
        price = Decimal(str(price)) 
        if self.discount_type == 'percentage':
            return price - (price * self.discount_value / 100)
        return max(price - self.discount_value, 0)  # prevent negative price

    def __str__(self):
        return self.code

class CouponUsage(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coupon_usages')
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('coupon', 'user')  # prevents duplicate usage per user

    def __str__(self):
        return f"{self.user} used {self.coupon.code}"


class Booking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE)
    club = models.ForeignKey(Club, on_delete=models.SET_NULL, null=True)
    player = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    final_price = models.DecimalField(max_digits=10, decimal_places=2)
    deposit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=None)
    status = models.PositiveSmallIntegerField(choices=BookingStatus.choices, default=BookingStatus.PENDING_MANAGER)
    payment_status = models.PositiveSmallIntegerField(choices=PayStatus.choices, default=PayStatus.UNKNOWN, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    note_owner = models.TextField(blank=True)
    note_admin = models.TextField(blank=True)
    by_owner = models.BooleanField(default=False)# if False the booking done by player
    phone_validator = RegexValidator(regex=r'^09\d{8}$', message=_('Phone number must start with "09" and contain exactly 10 digits (e.g., 0912345678).'))
    phone = models.CharField(validators=[phone_validator], max_length=10, null=True, blank=True, default=None)
    is_challenge = models.BooleanField(default=False)
    coupon = models.ForeignKey(
        'Coupon',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings'
    )


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


class BookingEquipment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE)
    equipment = models.ForeignKey(ClubEquipment, on_delete=models.CASCADE)
    equipment_def = models.ForeignKey(Equipment, on_delete=models.CASCADE)
    # name = models.CharField(max_length=100)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

