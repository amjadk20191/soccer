# booking_manager/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Booking, Review, BookingStatus, BookingEquipment


@admin.register(BookingEquipment)
class BookingEquipmentAdmin(admin.ModelAdmin):
    list_display = [
        'id_short',
        'quantity',
        'price',
        'created_at'
    ]
    list_filter = [
        'created_at',
        'equipment__club',
        'equipment__equipment__name'
    ]
    search_fields = [
        'booking__id',
        'equipment__club__name',
        'equipment__equipment__name'
    ]
    date_hierarchy = 'created_at'
    autocomplete_fields = ['booking', 'equipment']
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'total_price'
    ]
    
    fieldsets = (
        ('IDs', {
            'fields': ('id',),
            'classes': ('collapse',)
        }),
        ('Relations', {
            'fields': ('booking', 'equipment', 'equipment_def')
        }),
        ('Item Details', {
            'fields': ('quantity', 'price', 'is_challenge', 'by_owner')
        }),
        ('Financial', {
            'fields': ('total_price',),
            'description': 'Auto-calculated from quantity × price'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def id_short(self, obj):
        """Display shortened UUID"""
        return str(obj.id)[:8]
    id_short.short_description = 'ID'
    
    
    

    def total_price(self, obj):
        """Calculate total price"""
        return 0 #obj.quantity * obj.price
    total_price.short_description = 'Total Price'
    
    def get_queryset(self, request):
        """Optimize queries with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('booking', 'equipment', 'equipment__club', 'equipment__equipment')


@admin.action(description=_('Mark selected bookings as Completed'))
def mark_completed(modeladmin, request, queryset):
    queryset.update(status=BookingStatus.COMPLETED)

@admin.action(description=_('Mark selected bookings as Canceled'))
def mark_canceled(modeladmin, request, queryset):
    queryset.update(status=BookingStatus.CANCELED)

@admin.action(description=_('Mark selected bookings as Rejected'))
def mark_rejected(modeladmin, request, queryset):
    queryset.update(status=BookingStatus.REJECT)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """Admin configuration for Booking model"""
    
    def status_badge(self, obj):
        """Display status with color-coded badge"""
        status_colors = {
            BookingStatus.PENDING_MANAGER: '#f39c12',  # Orange
            BookingStatus.PENDING_PLAYER: '#3498db',   # Blue
            BookingStatus.PENDING_PAY: '#9b59b6',      # Purple
            BookingStatus.COMPLETED: '#27ae60',        # Green
            BookingStatus.CANCELED: '#e74c3c',         # Red
            BookingStatus.REJECT: '#95a5a6',           # Gray
        }
        status_labels = dict(BookingStatus.choices)
        color = status_colors.get(obj.status, '#7f8c8d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color, status_labels[obj.status]
        )
    status_badge.short_description = _('Status')
    
    def booking_duration(self, obj):
        """Display formatted duration"""
        return f"{obj.start_time} - {obj.end_time}"
    booking_duration.short_description = _('Time Slot')
    
    list_display = (
        'id','club' , 'pitch', 'player', 'phone', 'date', 'booking_duration',
        'price', 'final_price', 'status_badge', 'created_at', 'status',
        'payment_status', 'deposit', 'note_owner', 'by_owner',
    )
    list_filter = (
        'status', 'date', 'created_at', 'updated_at',
        'pitch__club'
    )
    search_fields = (
        'id', 'pitch__name', 'pitch__club__name',
        'player__phone', 'player__full_name'
    )
    autocomplete_fields = ('pitch', 'player')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    date_hierarchy = 'date'
    list_select_related = ('pitch', 'player', 'pitch__club')
    list_editable = ('status',)  # Quick edit in list view
    
    fieldsets = (
        (_('Booking Details'), {
            'fields': (
                'club', 'pitch', 'player', 'phone', 'date',
                'start_time', 'end_time', 'price', 'final_price', 'status',
                'payment_status', 'deposit', 'note_owner', 'by_owner',
            )
        }),
        (_('Admin Notes'), {
            'fields': ('note_admin',),
            'classes': ('collapse',)
        }),
        (_('System Information'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [mark_completed, mark_canceled, mark_rejected]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Admin configuration for Review model"""
    
    def rating_stars(self, obj):
        """Display rating as stars"""
        return format_html(
            '<span style="color: #f1c40f;">{}</span>',
            '★' * obj.rating + '☆' * (5 - obj.rating)
        )
    rating_stars.short_description = _('Rating')
    
    def comment_short(self, obj):
        """Truncate comment for list display"""
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
    comment_short.short_description = _('Comment')
    
    list_display = (
        'id', 'club', 'booking', 'player', 'rating_stars',
        'comment_short', 'created_at'
    )
    list_filter = (
        'rating', 'created_at', 'club'
    )
    search_fields = (
        'club__name', 'player__phone', 'player__full_name',
        'booking__id', 'comment'
    )
    autocomplete_fields = ('club', 'booking', 'player')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    list_select_related = ('club', 'booking', 'player')
    
    fieldsets = (
        (_('Review Information'), {
            'fields': ('booking', 'player', 'club', 'rating', 'comment')
        }),
        (_('System Information'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )