from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from .models import Team, TeamMember, MemberStatus
from .serializers import UserTeamListSerializer, TeamDetailsSerializer


class UserTeamsListView(APIView):
    """
    API endpoint to list all teams that the authenticated user belongs to.
    
    Returns only teams where:
    - User is an active member (status = ACTIVE)
    - Team is active (is_active = True)
    
    Shows: team_id, team_name, is_captain, is_active, joined_at
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Get all teams the user belongs to.
        User is identified from JWT token (request.user).
        Uses .only() for faster query performance and UserTeamListSerializer.
        """
        user = request.user
        
        # Get all team memberships where:
        # - User is the player
        # - Member status is ACTIVE
        # - Team is active (is_active = True) - filter ensures only active teams are returned
        # Use .only() to fetch only required fields for better performance
        # Use select_related to avoid N+1 queries for team data
        team_memberships = TeamMember.objects.filter(
            player=user,
            status=MemberStatus.ACTIVE,
            team__is_active=True  # Filter: only return teams where is_active = True
        ).select_related('team').only(
            # TeamMember fields needed by serializer
            'id',
            'is_captain',
            'joined_at',
            'team_id',
            # Team fields needed by serializer (via select_related)
            # Note: team__is_active is included for serializer response, 
            # though it will always be True due to the filter above
            'team__id',
            'team__name',
            'team__logo',
            'team__challenge_mode'
        ).order_by('-joined_at')
        
        # Serialize the data using UserTeamListSerializer
        serializer = UserTeamListSerializer(team_memberships, many=True, context={'request': request})
        
        return Response({
            'teams': serializer.data,
            'count': len(serializer.data)
        }, status=status.HTTP_200_OK)


class TeamDetailsView(APIView):
    """
    API endpoint to get detailed information about a specific team.
    
    User must be a member of the team to view details.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, team_id):
        """
        Get detailed team information including team members.
        
        Args:
            team_id: UUID of the team
            
        Returns:
            Detailed team information including statistics and all team members
        """
        user = request.user
        
        # Get the team with prefetched members for better performance
        # Use .only() to fetch only required fields for faster queries
        # Prefetch team members with their player information to avoid N+1 queries
        team = get_object_or_404(
            Team.objects.only(
                # Team fields needed by serializer
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
                'created_at'
            ).prefetch_related(
                Prefetch(
                    'teammember_set',
                    queryset=TeamMember.objects.filter(
                        status__in=[MemberStatus.ACTIVE, MemberStatus.INACTIVE]  # Only ACTIVE or INACTIVE members (exclude OUT)
                    ).select_related('player').only(
                        # TeamMember fields needed by serializer
                        'id',
                        'is_captain',
                        'joined_at',
                        'status',  # Needed for status_display
                        'player_id',
                        # Player fields needed by serializer (via select_related)
                        'player__id',
                        'player__full_name',
                        'player__username'
                    ).order_by('-is_captain', 'joined_at')
                )
            ),
            id=team_id,
            is_active=True
        )
        
        # Check if user is a member of this team (any status)
        is_member = TeamMember.objects.filter(
            team=team,
            player=user
        ).exists()
        
        if not is_member:
            raise PermissionDenied(
                detail="You must be a member of this team to view its details."
            )
        
        # Serialize team details (includes members)
        # Pass request context for absolute URL building
        serializer = TeamDetailsSerializer(team, context={'request': request})
        
        return Response(serializer.data, status=status.HTTP_200_OK)
