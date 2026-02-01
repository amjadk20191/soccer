from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserTeamsListView, TeamDetailsView

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
    # List all teams the authenticated user belongs to
    path('my-teams/', UserTeamsListView.as_view(), name='user-teams-list'),
    # Get detailed information about a specific team
    path('details/<uuid:team_id>/', TeamDetailsView.as_view(), name='team-details'),
]