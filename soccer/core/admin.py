# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Notification


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom UserAdmin for the User model with phone as username"""
    
    model = User
    
    # Fieldsets for editing existing users
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        (_('Personal Info'), {
            'fields': ('full_name', 'username', 'birthday', 'height', 'weight', 'foot_preference')
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'role', 'groups', 'user_permissions')
        }),
        (_('Booking Stats'), {
            'fields': ('booking_time', 'cancel_time')
        }),
        (_('Important Dates'), {
            'fields': ('last_login', 'created_at', 'updated_at')
        }),
    )
    
    # Fieldsets for adding new users
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'phone', 'password1', 'password2', 'full_name', 'username',
                'birthday', 'height', 'weight', 'foot_preference', 'role',
                'is_staff', 'is_active'
            ),
        }),
    )
    
    # List view configuration
    list_display = ('phone', 'full_name', 'username', 'role', 'is_staff', 'is_active', 'age', 'created_at')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'role', 'foot_preference', 'created_at')
    search_fields = ('phone', 'full_name', 'username')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'last_login', 'age')
    
    # Django auth specific configurations
    filter_horizontal = ('groups', 'user_permissions',)
    
    # Specify phone as the username field for authentication
    # This tells Django admin to use 'phone' instead of 'username'
    username_field = 'phone'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin configuration for Notification model"""
    
    list_display = ('title', 'user', 'sender', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('title', 'message', 'user__phone', 'user__full_name', 'sender__phone', 'sender__full_name')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('user', 'sender')  # Better performance for large user tables
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'