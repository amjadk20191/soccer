# clubs/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Club, ClubPricing, Pitch, ReservationTypeHoure


class ClubPricingInline(admin.TabularInline):
    """Inline admin for ClubPricing"""
    model = ClubPricing
    extra = 0
    fields = ('type', 'day_of_week', 'date', 'start_time', 'end_time', 'percent')


class PitchInline(admin.TabularInline):
    """Inline admin for Pitch"""
    model = Pitch
    extra = 0
    fields = ('name', 'type', 'size_width', 'size_high', 'is_active', 'price_first', 'price_second', 'time_interval', 'image')
    readonly_fields = ('created_at', 'updated_at')
    show_change_link = True


class ReservationTypeHoureInline(admin.TabularInline):
    """Inline admin for ReservationTypeHoure"""
    model = ReservationTypeHoure
    extra = 0
    fields = ('minutes',)
    show_change_link = True


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    """Admin configuration for Club model"""
    
    list_display = (
        'name', 'manager', 'address', 'open_time', 'close_time',
        'rating_avg', 'rating_count', 'is_active', 'flexible_reservation', 'created_at', 'is_active'
    )
    list_filter = (
        'flexible_reservation', 'created_at', 'updated_at',
        'rating_avg', 'working_days'
    )
    search_fields = (
        'name', 'address', 'manager__phone', 'manager__full_name',
        'description'
    )
    readonly_fields = ('created_at', 'updated_at', 'rating_avg', 'rating_count')
    autocomplete_fields = ('manager',)
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    list_select_related = ('manager',)
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'manager', 'description', 'logo', 'is_active')
        }),
        (_('Location & Contact'), {
            'fields': ('address', ('latitude', 'longitude'))
        }),
        (_('Working Schedule'), {
            'fields': ('open_time', 'close_time', 'working_days')
        }),
        (_('Rating Statistics'), {
            'fields': ('rating_avg', 'rating_count'),
            'description': _('Automatically calculated based on user reviews')
        }),
        (_('Reservation Settings'), {
            'fields': ('flexible_reservation',)
        }),
        (_('System Information'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    # inlines = [ClubPricingInline, PitchInline, ReservationTypeHoureInline]


@admin.register(ClubPricing)
class ClubPricingAdmin(admin.ModelAdmin):
    """Admin configuration for ClubPricing model"""
    
    list_display = (
        'club', 'type', 'get_scheduled_date', 'start_time', 'end_time', 'percent'
    )
    list_filter = ('type', 'day_of_week', 'club')
    search_fields = ('club__name',)
    autocomplete_fields = ('club',)
    ordering = ('club', 'type', 'day_of_week', 'date')
    list_select_related = ('club',)
    
    def get_scheduled_date(self, obj):
        """Display either day_of_week or date based on type"""
        if obj.type == 1:  # Weekday
            weekdays = [_('Saturday'), _('Sunday'), _('Monday'), _('Tuesday'), _('Wednesday'), 
                       _('Thursday'), _('Friday')]
            day_num = obj.day_of_week or 0
            return weekdays[day_num] if day_num < len(weekdays) else f"Day {day_num}"
        else:  # Date
            return obj.date or '-'
    get_scheduled_date.short_description = _('Scheduled For')


@admin.register(Pitch)
class PitchAdmin(admin.ModelAdmin):
    """Admin configuration for Pitch model"""
    
    list_display = (
        'name', 'club', 'type', 'size_width', 'size_high', 'is_active',
        'price_first', 'price_second', 'created_at'
    )
    list_filter = (
        'is_active', 'type', 'club', 'created_at', 'updated_at'
    )
    search_fields = (
        'name', 'club__name', 'type', 'size_width', 'size_high'
    )
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('club',)
    ordering = ('club', 'name')
    date_hierarchy = 'created_at'
    list_select_related = ('club',)
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('club', 'name', 'type', 'size_width', 'size_high', 'image')
        }),
        (_('Pricing & Timing'), {
            'fields': ('price_first', 'price_second', 'time_interval')
        }),
        (_('Status'), {
            'fields': ('is_active',),
            'description': _('Inactive pitches will not be available for booking')
        }),
        (_('System Information'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ReservationTypeHoure)
class ReservationTypeHoureAdmin(admin.ModelAdmin):
    """Admin configuration for ReservationTypeHoure model"""
    
    list_display = ('club', 'minutes')
    list_filter = ('club',)
    search_fields = ('club__name',)
    autocomplete_fields = ('club',)
    ordering = ('club', 'minutes')
    list_select_related = ('club',)