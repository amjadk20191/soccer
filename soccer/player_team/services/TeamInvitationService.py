from django.db import transaction
from django.db.models import Q
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from core.models import User
from ..models import Team, TeamMember, Request, MemberStatus


class RequestStatus:
    """Request status constants"""
    PENDING = 1
    ACCEPTED = 2
    REJECTED = 3


class TeamInvitationService:
    """
    Service class for managing team invitations.
    
    Handles:
    - Captain inviting players to team by username
    - Players accepting or rejecting invitations
    - Creating team memberships upon acceptance
    """
    
    @classmethod
    def _check_team_member_limit(cls, team_id):
        """
        Check if team has reached the maximum member limit.
        
        Args:
            team_id: UUID of the team
            
        Returns:
            Tuple of (is_within_limit: bool, current_count: int, max_allowed: int)
            
        Raises:
            ValidationError: If team has reached maximum member limit
        """
        max_members = getattr(settings, 'MAX_TEAM_MEMBERS', 7)
        
        # Count active members efficiently using .count()
        current_count = TeamMember.objects.filter(
            team_id=team_id,
            status__in=[MemberStatus.ACTIVE, MemberStatus.INACTIVE]
        ).count()
        
        if current_count >= max_members:
            raise ValidationError(
                detail=f"Team has reached the maximum limit of {max_members} members. "
                       f"Current members: {current_count}"
            )
        
        return True, current_count, max_members
    
    @classmethod
    def invite_player_to_team(cls, captain_id, team_id, username):
        """
        Captain invites a player to join the team by username.
        
        Args:
            captain_id: UUID of the captain (from JWT token)
            team_id: UUID of the team
            username: Username of the player to invite
            
        Returns:
            Request object
            
        Raises:
            ValidationError: If validation fails
            PermissionDenied: If user is not captain
            NotFound: If team or player not found
        """
        # Get team and verify captain
        team = Team.objects.only('id', 'captain_id', 'is_active').filter(
            id=team_id,
            is_active=True
        ).first()
        
        if not team:
            raise NotFound(detail="Team not found or is inactive.")
        
        if team.captain_id != captain_id:
            raise PermissionDenied(detail="Only the team captain can invite players.")
        
        # Get player by username
        player = User.objects.only('id', 'username').filter(username=username).first()
        
        if not player:
            raise NotFound(detail=f"Player with username '{username}' not found.")
        
        # Check if player is already a member
        existing_member = TeamMember.objects.filter(
            team_id=team_id,
            player_id=player.id,
            status__in=[MemberStatus.ACTIVE, MemberStatus.INACTIVE]
        ).exists()
        
        if existing_member:
            raise ValidationError(detail="Player is already a member of this team.")
        
        # Check if there's already a pending request
        existing_request = Request.objects.filter(
            team_id=team_id,
            player_id=player.id,
            status=RequestStatus.PENDING,
            recruitment_post__isnull=True
        ).exists()
        
        if existing_request:
            raise ValidationError(detail="A pending invitation already exists for this player.")
        
        # Check if team has reached maximum member limit
        cls._check_team_member_limit(team_id)
        
        # Create invitation request
        with transaction.atomic():
            request = Request.objects.create(
                recruitment_post=None,
                team_id=team_id,
                player_id=player.id,
                status=RequestStatus.PENDING
            )
        
        return request
    
    @classmethod
    def respond_to_invitation(cls, player_id, request_id, accept):
        """
        Player accepts or rejects a team invitation.
        
        Args:
            player_id: UUID of the player (from JWT token)
            request_id: UUID of the invitation request
            accept: Boolean - True to accept, False to reject
            
        Returns:
            Tuple of (Request object, TeamMember object if accepted else None)
            
        Raises:
            ValidationError: If validation fails
            PermissionDenied: If user is not the invited player
            NotFound: If request not found
        """
        # Get request with team info
        request = Request.objects.select_related('team').only(
            'id',
            'team_id',
            'player_id',
            'status',
            'recruitment_post_id',
            'team__id',
            'team__is_active'
        ).filter(
            id=request_id,
            recruitment_post__isnull=True  # Only direct invitations, not recruitment post requests
        ).first()
        
        if not request:
            raise NotFound(detail="Invitation request not found.")
        
        # Verify the request is for this player
        if request.player_id != player_id:
            raise PermissionDenied(detail="This invitation is not for you.")
        
        # Check if request is already processed
        if request.status != RequestStatus.PENDING:
            raise ValidationError(detail="This invitation has already been processed.")
        
        # Check if team is still active
        if not request.team.is_active:
            raise ValidationError(detail="The team is no longer active.")
        
        with transaction.atomic():
            if accept:
                # Check if player is already a member
                existing_member = TeamMember.objects.filter(
                    team_id=request.team_id,
                    player_id=player_id,
                    status__in=[MemberStatus.ACTIVE, MemberStatus.INACTIVE]
                ).exists()
                
                if existing_member:
                    raise ValidationError(detail="You are already a member of this team.")
                
                # Check if team has reached maximum member limit before accepting
                cls._check_team_member_limit(request.team_id)
                existing_team = TeamMember.objects.only('id').filter(
                    player_id=player_id,
                    status=MemberStatus.ACTIVE,
                    team__is_active=True 
                ).count()
        
                if existing_team > settings.MAX_TEAMS:
                    raise ValidationError(detail="You are already in 5 active team.")
                        # Create team membership
                team_member = TeamMember.objects.create(
                    team_id=request.team_id,
                    player_id=player_id,
                    status=MemberStatus.ACTIVE,
                    is_captain=False  # New members are not captains
                )
                
                # Update request status to accepted
                request.status = RequestStatus.ACCEPTED
                request.save(update_fields=['status'])
                
                return request, team_member
            else:
                # Update request status to rejected
                request.status = RequestStatus.REJECTED
                request.save(update_fields=['status'])
                
                return request, None
    
    @classmethod
    def get_user_invitations(cls, player_id):
        """
        Get all invitation requests for the authenticated user.
        
        Includes:
        - Direct invitations (recruitment_post is null)
        - Recruitment post requests where is_open=True and post_type=2
        
        Args:
            player_id: UUID of the player (from JWT token)
            
        Returns:
            QuerySet of Request objects
        """
        # Get all requests for this player:
        # - Direct invitations (recruitment_post is null), OR
        # - Recruitment post requests where is_open=True and post_type=2
        # Only return invitations for active teams
        invitations = Request.objects.filter(
            player_id=player_id,
            team__is_active=True,
            status=1 # pending
        ).filter(
            Q(recruitment_post__isnull=True) | 
            Q(recruitment_post__is_open=True, recruitment_post__post_type=2)
        ).select_related('team', 'recruitment_post').only(
            'id',
            'team_id',
            'player_id',
            'status',
            'created_at',
            'recruitment_post_id',
            'team__id',
            'team__name',
            'team__logo',
            'team__is_active',
            'recruitment_post__type',
            'recruitment_post__description'
        ).order_by('-created_at')
        
        return invitations
    
    @classmethod
    def search_users_by_username(cls, username_filter, limit=10):
        """
        Search users by username filter and return top matching users.
        
        Args:
            username_filter: String to filter usernames (case-insensitive)
            limit: Maximum number of results to return (default: 10)
            
        Returns:
            QuerySet of User objects matching the filter
        """
        if not username_filter or not username_filter.strip():
            return User.objects.none()
        
        # Search for users whose username contains the filter (case-insensitive)
        # Order by username for consistent results
        users = User.objects \
                .filter(username__icontains=username_filter.strip()) \
                .order_by('username') \
                .values_list('username', flat=True)[:limit]
        
        return users
    
    @classmethod
    def remove_player_from_team(cls, user_id, team_id, player_id_to_remove=None):
        """
        Remove a player from a team by setting status to OUT.
        
        Two scenarios:
        1. Captain removes a player: player_id_to_remove must be provided
        2. Player removes themselves: player_id_to_remove is None (uses user_id)
        
        Args:
            user_id: UUID of the user making the request (from JWT token)
            team_id: UUID of the team
            player_id_to_remove: UUID of player to remove (None if player removing themselves)
            
        Returns:
            TeamMember object with updated status
            
        Raises:
            ValidationError: If validation fails
            PermissionDenied: If user doesn't have permission
            NotFound: If team or player not found
        """
        # Get team with optimized query
        team = Team.objects.only('id', 'captain_id', 'is_active').filter(
            id=team_id,
            is_active=True
        ).first()
        
        if not team:
            raise NotFound(detail="Team not found or is inactive.")
        
        # Determine which player to remove
        if player_id_to_remove:
            # Captain removing a player
            if team.captain_id != user_id:
                raise PermissionDenied(detail="Only the team captain can remove players.")
            
            target_player_id = player_id_to_remove
            
            # Prevent captain from removing themselves
            if target_player_id == user_id:
                raise ValidationError(detail="Captain cannot remove themselves from the team.")
        else:
            # Player removing themselves
            target_player_id = user_id
        
        # Get team member with optimized query
        team_member = TeamMember.objects.only(
            'id'
        ).filter(
            team_id=team_id,
            player_id=target_player_id,
            status__in=[MemberStatus.ACTIVE, MemberStatus.INACTIVE],  # Only active/inactive can be removed
            is_captain=False
        ).first()
        
        if not team_member:
            raise NotFound(detail="Player is not an active member of this team.")

        
        # Update status to OUT and set leave_at timestamp
        with transaction.atomic():
            team_member.status = MemberStatus.OUT
            team_member.leave_at = timezone.now()
            team_member.save(update_fields=['status', 'leave_at'])
        
        return team_member

