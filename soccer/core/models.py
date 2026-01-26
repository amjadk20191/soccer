# accounts/models.py
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

import uuid





class FootPreference(models.IntegerChoices):
    LEFT = 1, _('Left')
    RIGHT = 2, _('Right')
    BOTH = 3, _('Both')


class CustomUserManager(BaseUserManager):
    """Custom manager for User model with phone as the unique identifier"""
    
    def create_user(self, phone, password=None, **extra_fields):
        """Create and save a regular user"""
        if not phone:
            raise ValueError(_('phone is required'))
        
        
        user = self.model(phone=phone, **extra_fields)
        
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
            
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        """Create and save a superuser"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 3)
        
        return self.create_user(phone, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model representing system users.
    Uses phone as the primary authentication field.
    """
    
    # Primary Key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    
    # Personal Information
    full_name = models.CharField(max_length=255, verbose_name=_('Full Name'))
    username = models.CharField(max_length=150, verbose_name=_('Username'))
    
    # Contact Information
    phone_validator = RegexValidator(regex=r'^09\d{8}$', message=_('Phone number must start with "09" and contain exactly 10 digits (e.g., 0912345678).'))
    phone = models.CharField(validators=[phone_validator], max_length=10, unique=True, verbose_name=_('Phone Number'))
    
    # Role & Permissions
    role = models.PositiveSmallIntegerField(default=1, verbose_name=_('Role'))
    
    # Physical Attributes
    birthday = models.DateField(verbose_name=_('Birthday'))
    height = models.PositiveSmallIntegerField()
    weight = models.PositiveSmallIntegerField()
    foot_preference = models.SmallIntegerField(choices=FootPreference.choices)

    # Booking Information
    booking_time = models.PositiveIntegerField(default=0, verbose_name=_('Booking Time'))
    cancel_time = models.PositiveIntegerField(default=0, verbose_name=_('Cancel Time'))

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created At'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated At'))

    # Django Required Fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    
    # Manager
    objects = CustomUserManager()
    
    # Authentication Configuration
    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['full_name', 'username', 'birthday', 'height', 'weight', 'foot_preference']
    
    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        db_table = 'users'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['username'])
        ]
    
    def __str__(self):
        return self.phone or str(self.id)
    
    @property
    def age(self):
        """Calculate user's age based on birthday"""
        if not self.birthday:
            return None
        today = timezone.now().date()
        return today.year - self.birthday.year - (
            (today.month, today.day) < (self.birthday.month, self.birthday.day)
        )





class Notification(models.Model):
    """General system notifications"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sended_notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    notification_type = models.CharField(max_length=100)
    class Meta:
        db_table = 'notifications'
        verbose_name = _('Notification')
        verbose_name_plural = _('Notifications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
        ]