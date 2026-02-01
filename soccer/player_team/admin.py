# player_team/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Team, TeamMember, RecruitmentPost, Request, MemberStatus


class TeamMemberInline(admin.TabularInline):
    """Inline admin for TeamMember"""
    model = TeamMember
    extra = 0
    fields = ('player', 'status', 'is_captain', 'joined_at', 'leave_at')
    autocomplete_fields = ('player',)
    show_change_link = True


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    """Admin configuration for Team model"""
    
    def logo_preview(self, obj):
        """Display thumbnail of team logo"""
        if obj.logo:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 5px;" />',
                obj.logo.url
            )
        return _("No logo")
    logo_preview.short_description = _("Logo")
    
    def get_total_matches(self, obj):
        """Display total matches played"""
        return obj.total_matches
    get_total_matches.short_description = _("Total Matches")
    
    def get_win_rate(self, obj):
        """Display win percentage with formatting"""
        return f"{obj.win_rate:.1f}%"
    get_win_rate.short_description = _("Win Rate")
    
    list_display = (
        'name', 'captain', 'logo_preview', 'get_total_matches',
        'get_win_rate', 'challenge_mode', 'is_active', 'created_at'
    )
    list_filter = (
        'is_active', 'challenge_mode', 'created_at', 'updated_at',
        'captain'
    )
    search_fields = (
        'name', 'captain__phone', 'captain__full_name', 'address', 'time'
    )
    autocomplete_fields = ('captain',)
    readonly_fields = ('created_at', 'updated_at', 'get_total_matches', 'get_win_rate')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    list_select_related = ('captain',)
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'captain', 'address', 'time', 'logo')
        }),
        (_('Team Statistics'), {
            'fields': (
                'total_wins', 'total_losses', 'total_draw',
                'total_canceled', 'goals_scored', 'goals_conceded',
                'clean_sheet', 'failed_to_score',
                'get_total_matches', 'get_win_rate'
            ),
            'description': _('Automatically updated based on match results')
        }),
        (_('Settings'), {
            'fields': ('challenge_mode', 'is_active'),
            'description': _('Challenge mode allows the team to accept/reject match challenges')
        }),
        (_('System Information'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    # inlines = [TeamMemberInline]
    
    actions = ['toggle_challenge_mode', 'toggle_active_status']
    
    @admin.action(description=_('Toggle challenge mode for selected teams'))
    def toggle_challenge_mode(self, request, queryset):
        for team in queryset:
            team.challenge_mode = not team.challenge_mode
            team.save()
    
    @admin.action(description=_('Toggle active status for selected teams'))
    def toggle_active_status(self, request, queryset):
        for team in queryset:
            team.is_active = not team.is_active
            team.save()


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    """Admin configuration for TeamMember model"""
    
    def get_captain_status(self, obj):
        """Display captain status with icon"""
        if obj.is_captain:
            return format_html(
                '<span style="color: #f1c40f;">★ {}</span>', _('Captain')
            )
        return _('Member')
    get_captain_status.short_description = _('Role')
    
    list_display = (
        'id', 'team', 'player', 'status', 'get_captain_status',
        'joined_at', 'leave_at'
    )
    list_filter = (
        'status', 'is_captain', 'joined_at', 'leave_at', 'team'
    )
    search_fields = (
        'team__name', 'player__phone', 'player__full_name'
    )
    autocomplete_fields = ('team', 'player')
    readonly_fields = ('joined_at',)
    ordering = ('-joined_at',)
    list_select_related = ('team', 'player')
    
    fieldsets = (
        (_('Membership Details'), {
            'fields': ('team', 'player', 'status', 'is_captain')
        }),
        (_('Timeline'), {
            'fields': ('joined_at', 'leave_at')
        }),
    )


@admin.register(RecruitmentPost)
class RecruitmentPostAdmin(admin.ModelAdmin):
    """Admin configuration for RecruitmentPost model"""
    
    
    def get_poster(self, obj):
        """Display who posted (team or player)"""
        if obj.team:
            return format_html('{} <small>(Team)</small>', obj.team.name)
        elif obj.player:
            return format_html('{} <small>(Player)</small>', obj.player.full_name)
        return _("Unknown")
    get_poster.short_description = _('Posted By')
    
    def description_short(self, obj):
        """Truncate description for list display"""
        return obj.description[:60] + '...' if len(obj.description) > 60 else obj.description
    description_short.short_description = _('Description')
    
    def status_badge(self, obj):
        """Display open/closed status"""
        color = '#27ae60' if obj.is_open else '#e74c3c'
        text = _('Open') if obj.is_open else _('Closed')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color, text
        )
    status_badge.short_description = _('Status')
    
    list_display = (
        'id', 'get_poster', 'type', 'description_short',
        'status_badge', 'created_at', 'post_type'
    )
    list_filter = (
        'is_open', 'type', 'created_at'
    )
    search_fields = (
        'team__name', 'player__full_name', 'player__phone',
        'description', 'type'
    )
    autocomplete_fields = ('team', 'player')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    list_select_related = ('team', 'player')
    
    fieldsets = (
        (_('Post Details'), {
            'fields': ('type', 'description', 'is_open')
        }),
        (_('Who is Posting?'), {
            'fields': ('team', 'player'),
            'description': _('Fill team for "Team Seeking Player", player for "Player Seeking Team"')
        }),
        (_('System Information'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    """Admin configuration for Request model"""
    
    def get_requester(self, obj):
        """Display who made the request"""
        if obj.team:
            return format_html('{} <small>(Team)</small>', obj.team.name)
        elif obj.player:
            return format_html('{} <small>(Player)</small>', obj.player.full_name)
        return _("Unknown")
    get_requester.short_description = _('Requester')
    
    def get_recruitment_type(self, obj):
        """Display recruitment post type"""
        return obj.recruitment_post.type
    get_recruitment_type.short_description = _('Recruitment Type')
    
    list_display = (
        'id', 'recruitment_post', 'get_requester',
        'get_recruitment_type', 'created_at'
    )
    list_filter = (
        'created_at', 'recruitment_post__type', 'recruitment_post__is_open'
    )
    search_fields = (
        'recruitment_post__id', 'team__name',
        'player__phone', 'player__full_name'
    )
    autocomplete_fields = ('recruitment_post', 'team', 'player')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    list_select_related = ('recruitment_post', 'team', 'player')
    date_hierarchy = 'created_at'