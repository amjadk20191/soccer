# notifications/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import BookingStatusHistory, BookingNotification


@admin.register(BookingStatusHistory)
class BookingStatusHistoryAdmin(admin.ModelAdmin):
    """Admin for tracking booking status changes"""
    
    list_display = (
        'booking', 'status', 
        'date', 'start_time', 'end_time', 'change_at'
    )
    list_filter = (
        'status', 'date', 'change_at'
    )
    search_fields = (
        'booking__id', 'booking__user__phone', 
        'booking__user__full_name', 'old_status', 'new_status'
    )
    readonly_fields = ('change_at',)
    autocomplete_fields = ('booking',)
    ordering = ('-change_at',)
    date_hierarchy = 'change_at'


@admin.register(BookingNotification)
class BookingNotificationAdmin(admin.ModelAdmin):
    """Admin for booking change notifications"""
    
    list_display = (
        'id', 'booking', 'send_by', 'send_to', 
        'status', 'new_date', 'new_start_time', 'created_timestamp'
    )
    list_filter = ('status', 'new_date')
    search_fields = (
        'booking__id',
        'send_by__phone', 'send_by__full_name',
        'send_to__phone', 'send_to__full_name',
        'description'
    )
    readonly_fields = ('created_timestamp',)
    autocomplete_fields = ('booking', 'send_by', 'send_to')
    ordering = ('-id',)
    date_hierarchy = 'new_date'
    
    fieldsets = (
        (_('Notification Info'), {
            'fields': ('booking', 'send_by', 'send_to', 'status', 'description')
        }),
        (_('Original Booking Time'), {
            'fields': ('old_date', 'old_start_time', 'old_end_time')
        }),
        (_('New Booking Time'), {
            'fields': ('new_date', 'new_start_time', 'new_end_time')
        }),
    )
    
    def created_timestamp(self, obj):
        """Display creation time based on ID timestamp"""
        return obj.id.created if hasattr(obj.id, 'created') else '-'
    created_timestamp.short_description = _('Created At')