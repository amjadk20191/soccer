# player_team/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Challenge, ChallengeStatus


# Bulk actions for challenge management
@admin.action(description=_('Mark selected challenges as Accepted'))
def mark_accepted(modeladmin, request, queryset):
    queryset.update(status=ChallengeStatus.ACCEPTED)

@admin.action(description=_('Mark selected challenges as Rejected'))
def mark_rejected(modeladmin, request, queryset):
    queryset.update(status=ChallengeStatus.REJECTED)

@admin.action(description=_('Mark selected challenges as Canceled'))
def mark_canceled(modeladmin, request, queryset):
    queryset.update(status=ChallengeStatus.CANCELED)


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    """Admin configuration for Challenge model"""
    
    def status_badge(self, obj):
        """Display status with color-coded badge"""
        status_colors = {
            ChallengeStatus.PENDING: '#f39c12',    # Orange
            ChallengeStatus.ACCEPTED: '#27ae60',   # Green
            ChallengeStatus.REJECTED: '#e74c3c',   # Red
            ChallengeStatus.CANCELED: '#95a5a6',   # Gray
        }
        status_labels = dict(ChallengeStatus.choices)
        color = status_colors.get(obj.status, '#7f8c8d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color, status_labels[obj.status]
        )
    status_badge.short_description = _('Status')
    
    def challenge_duration(self, obj):
        """Display formatted time slot"""
        return f"{obj.start_time} - {obj.end_time}"
    challenge_duration.short_description = _('Time Slot')
    
    def match_score(self, obj):
        """Display match result score"""
        return f"{obj.result_team} - {obj.result_challenged_team}"
    match_score.short_description = _('Score')
    
    list_display = (
        'id', 'team', 'challenged_team', 'pitch', 'date',
        'challenge_duration', 'match_score', 'status_badge',
        'created_by', 'created_at','status'
    )
    list_filter = (
        'status', 'date', 'created_at', 'updated_at',
        'pitch__club'
    )
    search_fields = (
        'team__name', 'challenged_team__name',
        'pitch__name', 'pitch__club__name',
        'created_by__phone', 'created_by__full_name'
    )
    autocomplete_fields = (
        'booking', 'team', 'challenged_team',
        'pitch', 'created_by'
    )
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    date_hierarchy = 'date'
    list_select_related = (
        'team', 'challenged_team', 'pitch',
        'pitch__club', 'created_by'
    )
    list_editable = ('status',)  # Quick status update in list view
    
    fieldsets = (
        (_('Challenge Details'), {
            'fields': (
                'team', 'challenged_team', 'pitch',
                'date', 'start_time', 'end_time'
            )
        }),
        (_('Match Results'), {
            'fields': ('result_team', 'result_challenged_team'),
            'description': _('Final scores for the match')
        }),
        (_('Status & Administration'), {
            'fields': ('status', 'note_admin')
        }),
        (_('Related Booking'), {
            'fields': ('booking',),
            'description': _('Associated booking if challenge was converted to a reservation')
        }),
        (_('System Information'), {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [mark_accepted, mark_rejected, mark_canceled]