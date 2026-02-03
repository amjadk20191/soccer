from rest_framework import serializers
from .models import Team, TeamMember, MemberStatus, Request


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


class InvitePlayerSerializer(serializers.Serializer):
    """
    Serializer for captain to invite a player to team.
    """
    username = serializers.CharField(required=True, help_text="Username of the player to invite")
    
    def validate_username(self, value):
        """Validate username is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Username cannot be empty.")
        return value.strip()


class InvitationResponseSerializer(serializers.Serializer):
    """
    Serializer for invitation request response.
    """
    request_id = serializers.UUIDField(required=True, help_text="UUID of the invitation request")
    accept = serializers.BooleanField(required=True, help_text="True to accept, False to reject")


class InvitationRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for invitation request details.
    Includes recruitment post data when available (is_open=True, post_type=2).
    """
    team_id = serializers.UUIDField(source='team.id', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)
    team_logo = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    recruitment_post_type = serializers.SerializerMethodField()
    recruitment_post_description = serializers.SerializerMethodField()
    
    class Meta:
        model = Request
        fields = [
            'id',
            'team_id',
            'team_name',
            'team_logo',
            'status_display',
            'recruitment_post_type',
            'recruitment_post_description',
            'created_at'
        ]
        read_only_fields = ['id', 'status', 'created_at']
    
    def get_team_logo(self, obj):
        """Get team logo URL, building absolute URL if request context is available"""
        if obj.team and obj.team.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.team.logo.url)
            return obj.team.logo.url
        return None
    
    def get_recruitment_post_type(self, obj):
        """Get recruitment post type if available and conditions are met"""
        if obj.recruitment_post and obj.recruitment_post.is_open and obj.recruitment_post.post_type == 2:
            return obj.recruitment_post.type
        return None
    
    def get_recruitment_post_description(self, obj):
        """Get recruitment post description if available and conditions are met"""
        if obj.recruitment_post and obj.recruitment_post.is_open and obj.recruitment_post.post_type == 2:
            return obj.recruitment_post.description
        return None


class UserSearchSerializer(serializers.Serializer):
    """
    Serializer for user search filter.
    """
    username = serializers.CharField(required=True, help_text="Username filter to search for users")
    
    def validate_username(self, value):
        """Validate username filter is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Username filter cannot be empty.")
        return value.strip()


class UserSearchResultSerializer(serializers.Serializer):
    """
    Serializer for user search results.
    """
    id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)


class RemovePlayerSerializer(serializers.Serializer):
    """
    Serializer for captain to remove a player from team.
    """
    player_id = serializers.UUIDField(required=True, help_text="UUID of the player to remove from team")


class TeamCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new team.
    """

    class Meta:
        model = Team
        fields = [
                'name',
                'logo',
                'time',
                'address']
    def validate_name(self, value):
        """Validate team name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError({"name":"Team name cannot be empty."})
        return value.strip()


class TeamUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating team information (PATCH).
    All fields are optional.
    """
    class Meta:
        model = Team
        fields = [
                'name',
                'logo',
                'time',
                'address',
                'challenge_mode']
    def validate_name(self, value):
        """Validate team name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError({"name":"Team name cannot be empty."})
        return value.strip()

class TeamResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for team response data.
    """
    logo = serializers.SerializerMethodField()
    captain_id = serializers.UUIDField(source='captain.id', read_only=True)
    
    class Meta:
        model = Team
        fields = [
            'id',
            'name',
            'logo',
            'time',
            'address',
            'captain_id',
            'challenge_mode',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'is_active', 'created_at', 'updated_at']
    
    def get_logo(self, obj):
        """Get team logo URL, building absolute URL if request context is available"""
        if obj.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None


