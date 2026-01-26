# dashboard_manage/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Tag, Feature


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Admin for club/pitch tags/Feature"""
    
    list_display = ('name', 'logo_preview', 'id')
    search_fields = ('name',)
    readonly_fields = ('id',)
    
    def logo_preview(self, obj):
        """Display thumbnail of tag logo"""
        if obj.logo:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 5px;" />',
                obj.logo.url
            )
        return _("No logo")
    logo_preview.short_description = _("Logo Preview")


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    """Admin for associating tags with clubs"""
    
    list_display = ('club', 'tag', 'is_active', 'created_at', 'id')
    list_filter = ('is_active', 'club', 'tag', 'created_at')
    search_fields = (
        'club__name', 'club__manager__phone', 'club__manager__full_name',
        'tag__name'
    )
    autocomplete_fields = ('club', 'tag')
    readonly_fields = ('id', 'created_at')
    ordering = ('-created_at',)
    list_select_related = ('club', 'tag')
    date_hierarchy = 'created_at'