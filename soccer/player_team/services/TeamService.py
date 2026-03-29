from django.db import transaction
from django.conf import settings
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from ..models import Team, TeamMember, MemberStatus, MemberStatus


class TeamService:
    """
    Service class for managing team operations.
    
    Handles:
    - Creating teams (user becomes captain)
    - Updating team information
    - Deactivating teams (soft delete)
    """
    
    @classmethod
    def create_team(cls, captain_id, name, logo=None, time=None, address=None):
        """
        Create a new team with the authenticated user as captain.
        
        Args:
            captain_id: UUID of the captain (from JWT token)
            name: Team name
            logo: Team logo image (optional)
            time: Team time preference (optional)
            address: Team address (optional)
            
        Returns:
            Tuple of (Team object, TeamMember object)
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate team name
        if not name or not name.strip():
            raise ValidationError(detail={"error": "اسم الفريق مطلوب."})
        
        # Check if user is already in X active team
        existing_team = TeamMember.objects.only('id').filter(
            player_id=captain_id,
            status=MemberStatus.ACTIVE,
            team__is_active=True 
        ).count()
        
        if existing_team >= settings.MAX_TEAMS:
            raise ValidationError(detail={"error":f"أنت بالفعل في {settings.MAX_TEAMS} فرق نشطة."})
        
        # Create team and team member in a transaction
        with transaction.atomic():
            # Create team
            team = Team.objects.create(
                name=name.strip(),
                logo=logo,
                time=time.strip() if time else '',
                address=address.strip() if address else '',
                captain_id=captain_id
            )
            
            # Create team member (captain)
            team_member = TeamMember.objects.create(
                team=team,
                player_id=captain_id,
                status=MemberStatus.ACTIVE,
                is_captain=True
            )
        
        return team, team_member
    
  
    @classmethod
    def deactivate_team(cls, captain_id, team_id):
        """
        Deactivate a team (soft delete by setting is_active=False).
        
        Only the team captain can deactivate the team.
        
        Args:
            captain_id: UUID of the captain (from JWT token)
            team_id: UUID of the team
            
        Returns:
            Team object with is_active=False
            
        Raises:
            PermissionDenied: If user is not captain
            NotFound: If team not found
        """
        # Get team with optimized query
        team = Team.objects.only('id', 'captain_id', 'is_active').filter(
            id=team_id
        ).first()
        
        if not team:
            raise NotFound(detail={"error": "الفريق غير موجود."})
        
        # Verify user is the captain
        if team.captain_id != captain_id:
            raise PermissionDenied(detail={"error": "فقط قائد الفريق يمكنه إلغاء تنشيط الفريق."})
        
        # Check if team is already inactive
        if not team.is_active:
            raise ValidationError(detail={"error": "الفريق غير نشط بالفعل."})
        
        # Deactivate team
        with transaction.atomic():
            team.is_active = False
            team.save(update_fields=['is_active', 'updated_at'])
            TeamMember.objects.filter(team_id=team_id).update(status=MemberStatus.OUT)
        
        return team

