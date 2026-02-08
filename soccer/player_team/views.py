from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from .models import Team, TeamMember, MemberStatus, TeamImage
from .serializers import (
    UserTeamListSerializer, 
    TeamDetailsSerializer,
    InvitePlayerSerializer,
    InvitationResponseSerializer,
    InvitationRequestSerializer,
    UserSearchSerializer,
    UserSearchResultSerializer,
    RemovePlayerSerializer,
    TeamCreateSerializer,
    TeamUpdateSerializer,
    TeamResponseSerializer,
    TeamImageerializer
)
from player_team.services import TeamInvitationService, TeamService


class TeamImageListAPIView(generics.ListAPIView):
    queryset = TeamImage.objects.all()
    serializer_class = TeamImageerializer

class UserTeamsListView(APIView):
    """
    API endpoint to list all teams that the authenticated user belongs to.
    
    Returns only teams where:
    - User is an active member (status = ACTIVE)
    - Team is active (is_active = True)
    
    Shows: team_id, team_name, is_captain, is_active, joined_at
    """

    
    def get(self, request):
        """
        Get all teams the user belongs to.
        User is identified from JWT token (request.user).
        Uses .only() for faster query performance and UserTeamListSerializer.
        """
        user = request.user
        """
        team_memberships = TeamMember.objects.filter(
            player=user,
            status=MemberStatus.ACTIVE,
            team__is_active=True  
        ).select_related('team').only(
            'id',
            'is_captain',
            'joined_at',
            'team_id',
            'team__id',
            'team__name',
            'team__logo',
            'team__challenge_mode'
        ).order_by('-joined_at')
       """
       
        team_memberships = TeamMember.objects.filter(
            player=user,
            status=MemberStatus.ACTIVE,
            team__is_active=True
            ).select_related(
                'team', 
                'team__logo'  
            ).only(
                'id',
                'is_captain',
                'joined_at',
                'team_id',
                'team__name',
                'team__logo__logo',     
                'team__challenge_mode',
                'team__total_draw',
                'team__total_losses',
                'team__total_wins',
                'team__goals_scored',
                'team__clean_sheet'
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
            Team.objects.select_related('logo').only(
                # Team fields needed by serializer
                'id',
                'name',
                'address',
                'time',
                'logo__logo',
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


class InvitePlayerView(APIView):
    """
    API endpoint for captain to invite a player to join the team.
    
    Only the team captain can invite players.
    Creates a Request with PENDING status and null recruitment_post.
    """

    
    def post(self, request, team_id):
        """
        Invite a player to join the team by username.
        
        Args:
            team_id: UUID of the team
            
        Body:
            {
                "username": "player_username"
            }
        """
        # Get user ID from JWT token (fast access)
        captain_id = request.user.id
        
        # Validate input
        serializer = InvitePlayerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data['username']
        
        # Invite player using service
        TeamInvitationService.invite_player_to_team(
            captain_id=captain_id,
            team_id=team_id,
            username=username
        )
        
        
        return Response({
            'message': f'Invitation sent to {username}'      
              }, status=status.HTTP_201_CREATED)


class RespondToInvitationView(APIView):
    """
    API endpoint for player to accept or reject a team invitation.
    
    If accepted, creates a TeamMember with ACTIVE status.
    """

    
    def post(self, request):
        """
        Accept or reject a team invitation.
        
        Body:
            {
                "request_id": "uuid",
                "accept": true/false
            }
        """
        # Get user ID from JWT token (fast access)
        player_id = request.user.id
        
        # Validate input
        serializer = InvitationResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_id = serializer.validated_data['request_id']
        accept = serializer.validated_data['accept']
        
        # Process invitation response using service
        TeamInvitationService.respond_to_invitation(
            player_id=player_id,
            request_id=request_id,
            accept=accept
        )
        
        
        return Response({'message': 'Invitation accepted' if accept else 'Invitation rejected',}, status=status.HTTP_200_OK)


class MyInvitationsView(APIView):
    """
    API endpoint to get all invitation requests for the authenticated user.
    
    Returns all invitations (pending, accepted, rejected) sent to the user.
    """

    
    def get(self, request):
        """
        Get all invitation requests for the authenticated user.
        
        Returns invitations ordered by most recent first.
        """
        # Get user ID from JWT token (fast access)
        player_id = request.user.id
        
        # Get invitations using service
        invitations = TeamInvitationService.get_user_invitations(player_id=player_id)
        
        # Serialize response
        serializer = InvitationRequestSerializer(invitations, many=True, context={'request': request})
        
        return Response(serializer.data,
             status=status.HTTP_200_OK)


class SearchUsersView(APIView):
    """
    API endpoint to search users by username filter.
    
    Returns top 10 matching users based on username filter.
    """

    
    def get(self, request):
        """
        Search users by username filter.
        
        Query params:
            username: Username filter (required)
        """
        # Validate query parameter
        serializer = UserSearchSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        username_filter = serializer.validated_data['username']
        
        # Search users using service (returns top 10)
        users = TeamInvitationService.search_users_by_username(
            username_filter=username_filter,
            limit=10
        )
        
        
        return Response(
            {"users":users} 
         , status=status.HTTP_200_OK)


class RemovePlayerView(APIView):
    """
    API endpoint for captain to remove a player from the team.
    
    Only the team captain can remove players.
    Sets player status to OUT and records leave_at timestamp.
    """

    
    def post(self, request, team_id):
        """
        Remove a player from the team.
        
        Args:
            team_id: UUID of the team
            
        Body:
            {
                "player_id": "uuid"
            }
        """
        # Get user ID from JWT token (fast access)
        captain_id = request.user.id
        
        # Validate input
        serializer = RemovePlayerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        player_id_to_remove = serializer.validated_data['player_id']
        
        # Remove player using service
        team_member = TeamInvitationService.remove_player_from_team(
            user_id=captain_id,
            team_id=team_id,
            player_id_to_remove=player_id_to_remove
        )
        
        return Response({
            'message': 'Player removed from team successfully',
            'team_member_id': str(team_member.id),
            'status': team_member.status,
            'leave_at': team_member.leave_at
        }, status=status.HTTP_200_OK)


class LeaveTeamView(APIView):
    """
    API endpoint for player to leave a team (set their own status to OUT).
    
    Player can remove themselves from any team they belong to.
    Sets status to OUT and records leave_at timestamp.
    """

    
    def post(self, request, team_id):
        """
        Player leaves the team (removes themselves).
        
        Args:
            team_id: UUID of the team
        """
        # Get user ID from JWT token (fast access)
        player_id = request.user.id
        
        # Remove player using service (player_id_to_remove=None means self-removal)
        team_member = TeamInvitationService.remove_player_from_team(
            user_id=player_id,
            team_id=team_id,
            player_id_to_remove=None
        )
        
        return Response({
            'message': 'You have left the team successfully',
            'team_member_id': str(team_member.id),
            'status': team_member.status,
            'leave_at': team_member.leave_at
        }, status=status.HTTP_200_OK)


class CreateTeamView(APIView):
    """
    API endpoint for authenticated user to create a new team.
    
    The authenticated user becomes the team captain.
    Creates both Team and TeamMember records.
    """

    
    def post(self, request):
        """
        Create a new team.
        
        Body:
            {
                "name": "Team Name",
                "logo": <image file> (optional),
                "time": "Time preference" (optional),
                "address": "Address" (optional)
            }
        """
        # Get user ID from JWT token (fast access)
        captain_id = request.user.id
        
        # Validate input
        serializer = TeamCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create team using service
        TeamService.create_team(
            captain_id=captain_id,
            name=serializer.validated_data['name'],
            logo=serializer.validated_data.get('logo'),
            time=serializer.validated_data.get('time'),
            address=serializer.validated_data.get('address')
        )
        
        # Serialize response
        
        return Response({
            'message': 'Team created successfully',
        }, status=status.HTTP_201_CREATED)

class UpdateTeamView(generics.UpdateAPIView):
    http_method_names=['patch',]
    serializer_class = TeamUpdateSerializer

    def get_queryset(self):
        return Team.objects.filter(captain=self.request.user, is_active=True)

class _UpdateTeamView(APIView):
    """
    API endpoint for captain to update team information.
    
    Only the team captain can update team information.
    Supports partial updates (PATCH).
    """
    
    def patch(self, request, team_id):
        """
        Update team information.
        
        Args:
            team_id: UUID of the team
            
        Body (all fields optional):
            {
                "name": "New Team Name",
                "logo": <image file>,
                "time": "New time",
                "address": "New address",
                "challenge_mode": true/false
            }
        """
        # Get user ID from JWT token (fast access)
        captain_id = request.user.id
        
        # Validate input
        serializer = TeamUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Update team using service
        TeamService.update_team(
            captain_id=captain_id,
            team_id=team_id,
            **serializer.validated_data
        )
        
        # Serialize response
        
        return Response({
            'message': 'Team updated successfully',
        }, status=status.HTTP_200_OK)

class DeleteTeamView(APIView):
    """
    API endpoint for captain to deactivate a team (soft delete).
    
    Sets is_active=False instead of hard deletion.
    Only the team captain can deactivate the team.
    """

    
    def delete(self, request, team_id):
        """
        Deactivate a team (soft delete).
        
        Args:
            team_id: UUID of the team
        """
        # Get user ID from JWT token (fast access)
        captain_id = request.user.id
        
        # Deactivate team using service
        team = TeamService.deactivate_team(
            captain_id=captain_id,
            team_id=team_id
        )
        
        return Response({
            'message': 'Team deactivated successfully',
            'team_id': str(team.id)
        }, status=status.HTTP_200_OK)

