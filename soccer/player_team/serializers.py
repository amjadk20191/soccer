from rest_framework import serializers
from .models import Team, TeamMember, MemberStatus


class TeamMemberSerializer(serializers.ModelSerializer):
    """
    Serializer for team member information.
    Shows member details along with membership status.
    """
    member_id = serializers.UUIDField(source='player.id', read_only=True)
    full_name = serializers.CharField(source='player.full_name', read_only=True)
    username = serializers.CharField(source='player.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = TeamMember
        fields = [
            'id',
            'member_id',
            'full_name',
            'username',
            'status_display',
            'is_captain',
            'joined_at'
        ]

class UserTeamListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing teams that a user belongs to.
    Shows minimal team information with membership details.
    """
    team_id = serializers.UUIDField(source='team.id', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)
    team_logo = serializers.SerializerMethodField()
    challenge_mode = serializers.BooleanField(source='team.challenge_mode', read_only=True)
    joined_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = TeamMember
        fields = ['team_id', 'team_name', 'team_logo', 'is_captain', 'challenge_mode', 'joined_at']
    
    def get_team_logo(self, obj):
        """Get team logo URL, building absolute URL if request context is available"""
        if obj.team.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.team.logo.url)
            return obj.team.logo.url
        return None

class TeamDetailsSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed team information.
    Includes all team statistics, information, and team members.
    """
    total_matches = serializers.IntegerField(read_only=True)
    win_rate = serializers.FloatField(read_only=True)
    logo = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    members_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Team
        fields = [
            'id',
            'name',
            'address',
            'time',
            'logo',
            'total_wins',
            'total_losses',
            'total_draw',
            'total_canceled',
            'goals_scored',
            'goals_conceded',
            'clean_sheet',
            'failed_to_score',
            'challenge_mode',
            'total_matches',
            'win_rate',
            'members',
            'members_count',
            'created_at',
        ]
    
    def get_logo(self, obj):
        """Get team logo URL, building absolute URL if request context is available"""
        if obj.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None
    

    def get_members(self, obj):
        """Get all team members with ACTIVE or INACTIVE status (exclude OUT status)"""
        # Use prefetched data if available (already filtered to ACTIVE/INACTIVE)
        # Otherwise query the database with ACTIVE/INACTIVE status filter
        if hasattr(obj, 'teammember_set'):
            members = obj.teammember_set.all()  # Already filtered via Prefetch
        else:
            members = TeamMember.objects.filter(
                team=obj,
                status__in=[MemberStatus.ACTIVE, MemberStatus.INACTIVE]  # Only ACTIVE or INACTIVE
            ).select_related('player').order_by('-is_captain', 'joined_at')
        return TeamMemberSerializer(members, many=True).data
    
    def get_members_count(self, obj):
        """Get total number of team members with ACTIVE or INACTIVE status"""
        # Use prefetched data if available (already filtered to ACTIVE/INACTIVE)
        # Otherwise count only ACTIVE/INACTIVE members
        if hasattr(obj, 'teammember_set'):
            return obj.teammember_set.count()  # Already filtered via Prefetch
        return TeamMember.objects.filter(
            team=obj,
            status__in=[MemberStatus.ACTIVE, MemberStatus.INACTIVE]
        ).count()

