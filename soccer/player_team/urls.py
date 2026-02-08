from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserTeamsListView, 
    TeamDetailsView,
    InvitePlayerView,
    RespondToInvitationView,
    MyInvitationsView,
    SearchUsersView,
    RemovePlayerView,
    LeaveTeamView,
    CreateTeamView,
    UpdateTeamView,
    DeleteTeamView,
    TeamImageListAPIView
)

router = DefaultRouter()

urlpatterns = [
    path('team-images/', TeamImageListAPIView.as_view(), name='team-images-list'),
    # List all teams the authenticated user belongs to
    path('my-teams/', UserTeamsListView.as_view(), name='user-teams-list'),
    # Get detailed information about a specific team
    path('details/<uuid:team_id>/', TeamDetailsView.as_view(), name='team-details'),
    # Captain invites a player to team
    path('invite/<uuid:team_id>/', InvitePlayerView.as_view(), name='invite-player'),
    # Player accepts or rejects an invitation
    path('invitation/respond/', RespondToInvitationView.as_view(), name='respond-to-invitation'),
    # Get all invitation requests for authenticated user
    path('my-invitations/', MyInvitationsView.as_view(), name='my-invitations'),
    # Search users by username filter (returns top 10)
    path('search-users/', SearchUsersView.as_view(), name='search-users'),
    # Captain removes a player from team
    path('remove-player/<uuid:team_id>/', RemovePlayerView.as_view(), name='remove-player'),
    # Player leaves a team (removes themselves)
    path('leave-team/<uuid:team_id>/', LeaveTeamView.as_view(), name='leave-team'),
    # Create a new team
    path('create/', CreateTeamView.as_view(), name='create-team'),
    # Update team information
    path('update/<uuid:pk>/', UpdateTeamView.as_view(), name='update-team'),
    # Deactivate team (soft delete)
    path('delete/<uuid:team_id>/', DeleteTeamView.as_view(), name='delete-team'),
    
    path('', include(router.urls)),

]