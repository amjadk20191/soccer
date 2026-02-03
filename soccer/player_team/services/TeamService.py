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
            raise ValidationError(detail="Team name is required.")
        
        # Check if user is already in X active team
        existing_team = TeamMember.objects.only('id').filter(
            player_id=captain_id,
            status=MemberStatus.ACTIVE,
            team__is_active=True 
        ).count()
        
        if existing_team > settings.MAX_TEAMS:
            raise ValidationError(detail={"error":"You are already in 5 active team."})
        
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
    def update_team(cls, captain_id, team_id, **update_data):
        """
        Update team information.
        
        Only the team captain can update team information.
        
        Args:
            captain_id: UUID of the captain (from JWT token)
            team_id: UUID of the team
            **update_data: Dictionary of fields to update (logo, name, time, address, challenge_mode)
            
        Returns:
            Team object with updated data
            
        Raises:
            ValidationError: If validation fails
            PermissionDenied: If user is not captain
            NotFound: If team not found
        """
        # Get team with optimized query
        team = Team.objects.only(
            'id',
            'captain_id',
            'is_active',
            'name',
            'logo',
            'time',
            'address',
            'challenge_mode'
        ).filter(
            id=team_id,
            is_active=True
        ).first()
        
        if not team:
            raise NotFound(detail="Team not found or is inactive.")
        
        # Verify user is the captain
        if team.captain_id != captain_id:
            raise PermissionDenied(detail="Only the team captain can update team information.")
        
        # Validate and prepare update fields
        update_fields = []
        
        if 'name' in update_data:
            name = update_data['name']
            if name is not None:
                if not name.strip():
                    raise ValidationError(detail="Team name cannot be empty.")
                team.name = name.strip()
                update_fields.append('name')
        
        if 'logo' in update_data and update_data['logo'] is not None:
            team.logo = update_data['logo']
            update_fields.append('logo')
        
        if 'time' in update_data:
            time = update_data['time']
            if time is not None:
                team.time = time.strip() if time else ''
                update_fields.append('time')
        
        if 'address' in update_data:
            address = update_data['address']
            if address is not None:
                team.address = address.strip() if address else ''
                update_fields.append('address')
        
        if 'challenge_mode' in update_data:
            challenge_mode = update_data['challenge_mode']
            if challenge_mode is not None:
                team.challenge_mode = challenge_mode
                update_fields.append('challenge_mode')
        
        # Update team if there are fields to update
        if update_fields:
            update_fields.append('updated_at')  # Always update timestamp
            with transaction.atomic():
                team.save(update_fields=update_fields)
        
        return team
    
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
            raise NotFound(detail="Team not found.")
        
        # Verify user is the captain
        if team.captain_id != captain_id:
            raise PermissionDenied(detail="Only the team captain can deactivate the team.")
        
        # Check if team is already inactive
        if not team.is_active:
            raise ValidationError(detail="Team is already inactive.")
        
        # Deactivate team
        with transaction.atomic():
            team.is_active = False
            team.save(update_fields=['is_active', 'updated_at'])
        
        return team

