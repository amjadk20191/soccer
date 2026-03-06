# clubs/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import (Club, ClubPricing, Pitch, ReservationTypeHoure, Equipment, 
    ClubEquipment,
    BookingPriceStatistics,
    BookingNumStatistics,
    ClubHourlyStatistics,
    ClubEquipmentStatistics,
)
from django.utils.html import mark_safe

# ────────────────────────────────────────────────────────
# 1. Booking Price Statistics
# ────────────────────────────────────────────────────────

@admin.register(BookingPriceStatistics)
class BookingPriceStatisticsAdmin(admin.ModelAdmin):
    list_display = (
        'club', 'day', 
        'total_completed', 'total_pending', 

    )
    list_filter = ('day', 'club')
    search_fields = ('club__name',)
    date_hierarchy = 'day'
    ordering = ('-day',)

    # Make all fields read-only to prevent manual editing (Data is driven by signals)
    readonly_fields = [f.name for f in BookingPriceStatistics._meta.fields if f.name != 'id']

    def total_completed(self, obj):
        return obj.money_from_completed_owner + obj.money_from_completed_player
    total_completed.short_description = "Total Completed"

    def total_pending(self, obj):
        return obj.money_from_pending_pay_owner + obj.money_from_pending_pay_player
    total_pending.short_description = "Total Pending"

    # Performance optimization
    list_select_related = ('club',)

# ────────────────────────────────────────────────────────
# 2. Booking Number Statistics
# ────────────────────────────────────────────────────────

@admin.register(BookingNumStatistics)
class BookingNumStatisticsAdmin(admin.ModelAdmin):
    list_display = (
        'club', 'day', 
        'completed_num', 'pending_player_num', 'pending_pay_num', 
        'reject_num', 'no_Show_num', 'canceled_total'
    )
    list_filter = ('day', 'club')
    search_fields = ('club__name',)
    date_hierarchy = 'day'
    ordering = ('-day',)

    readonly_fields = [f.name for f in BookingNumStatistics._meta.fields if f.name != 'id']

    def canceled_total(self, obj):
        return (
            obj.canceled_num_from_completed_owner + 
            obj.canceled_num_from_completed_player + 
            obj.canceled_num_from_pending_pay_owner + 
            obj.canceled_num_from_pending_pay_player
        )
    canceled_total.short_description = "Total Canceled"

    # Group fields logically in the detail view
    fieldsets = (
        (None, {
            'fields': ('club', 'day')
        }),
        ('Completed & Pending', {
            'fields': (
                'completed_num', 'completed_num_owner', 
                'pending_player_num', 
                'pending_pay_num', 'pending_pay_num_owner'
            )
        }),
        ('Negative Outcomes', {
            'fields': (
                'reject_num', 'no_Show_num', 'disputed_num', 'expired_num'
            )
        }),
        ('Cancellation Details', {
            'fields': (
                'canceled_num_from_completed_owner', 'canceled_num_from_completed_player',
                'canceled_num_from_pending_pay_owner', 'canceled_num_from_pending_pay_player'
            )
        }),
    )

    list_select_related = ('club',)

# ────────────────────────────────────────────────────────
# 3. Club Hourly Statistics (Heatmap Data)
# ────────────────────────────────────────────────────────

@admin.register(ClubHourlyStatistics)
class ClubHourlyStatisticsAdmin(admin.ModelAdmin):
    list_display = ('club', 'pitch', 'date', 'hour', 'booked_minutes', 'utilization_percent')
    list_filter = ('date', 'hour', 'club', 'pitch')
    search_fields = ('club__name', 'pitch__name')
    date_hierarchy = 'date'
    ordering = ('-date', '-hour')

    readonly_fields = [f.name for f in ClubHourlyStatistics._meta.fields if f.name != 'id']

    def utilization_percent(self, obj):
        # Assuming standard hour is 60 mins max
        if obj.booked_minutes > 0:
            return f"{(obj.booked_minutes / 60) * 100:.1f}%"
        return "0%"
    utilization_percent.short_description = "Utilization"

    list_select_related = ('club', 'pitch')

# ────────────────────────────────────────────────────────
# 4. Club Equipment Statistics
# ────────────────────────────────────────────────────────

@admin.register(ClubEquipmentStatistics)
class ClubEquipmentStatisticsAdmin(admin.ModelAdmin):
    list_display = (
        'club', 'club_equipment', 'date', 
        'total_quantity', 'total_revenue'
    )
    list_filter = ('date', 'club')
    search_fields = ('club__name', 'club_equipment__name')
    date_hierarchy = 'date'
    ordering = ('-date',)

    readonly_fields = [f.name for f in ClubEquipmentStatistics._meta.fields if f.name != 'id']

    def total_quantity(self, obj):
        return obj.quantity_by_ower + obj.quantity_by_player
    total_quantity.short_description = "Total Qty"

    def total_revenue(self, obj):
        return obj.revenue_by_owner + obj.revenue_by_player
    total_revenue.short_description = "Total Revenue"

    list_select_related = ('club', 'club_equipment')

# ─────────────────────────────────────────────────────────────
# 5.  Global Admin Actions (Optional)
# ─────────────────────────────────────────────────────────────

def recalculate_statistics(modeladmin, request, queryset):
    """
    Admin action to trigger recalculation of selected statistics.
    Useful if signals missed updates or data drift occurred.
    """
    # Implementation depends on your recalculation logic
    modeladmin.message_user(request, f"Recalculation queued for {queryset.count()} records")

recalculate_statistics.short_description = "Recalculate selected statistics"

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
          'id',
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
        'id',
        'name', 'club', 'type', 'size_width', 'size_high', 'is_active',
        'price_first', 'price_second', 'created_at','is_deteted'
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
            'fields': ('id', 'club', 'name', 'type', 'size_width', 'size_high', 'image')
        }),
        (_('Pricing & Timing'), {
            'fields': ('price_first', 'price_second', 'time_interval')
        }),
        (_('Status'), {
            'fields': ('is_active','is_deteted'),
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



@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'description', 'image_tag']
    list_filter = ['name']
    search_fields = ['name', 'description']
    readonly_fields = ['image_preview']

    def image_tag(self, obj):
        if obj.image:
            return mark_safe(f'<img src="{obj.image.url}" width="50" height="50" style="object-fit: cover;" />')
        return "No Image"
    image_tag.short_description = 'Image'
    image_tag.allow_tags = True
    
    def image_preview(self, obj):
        if obj.image:
            return f'<img src="{obj.image.url}" width="300" style="max-height: 300px; object-fit: contain;" />'
        return "No Image"
    image_preview.short_description = 'Image Preview'
    image_preview.allow_tags = True


@admin.register(ClubEquipment)
class ClubEquipmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'club', 'equipment', 'price', 'quantity', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'club', 'equipment', 'created_at']
    search_fields = ['club__name', 'equipment__name']
    list_editable = ['quantity', 'is_active']
    date_hierarchy = 'created_at'
    autocomplete_fields = ['club', 'equipment']
    
    fieldsets = (
        ('Association', {
            'fields': ('club', 'equipment')
        }),
        ('Details', {
            'fields': ('price', 'quantity', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']