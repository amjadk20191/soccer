from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (TeamChallengesView, PlayerChallengesView, ChallengeDetailView, 
                    TeamDetailView, PlayerProfileView, SentChallengeListView, 
                    ChallengeCancelView, ChallengeTeamsView, CreateChallengeAPIView, 
                    PendingChallengeListView, ChallengeReplyView, ChallengeResultChoicesView)

router = DefaultRouter()

urlpatterns = [
    path('challenges/result-choices/', ChallengeResultChoicesView.as_view()),

    path('teams_challenges/<uuid:team_id>/',     TeamChallengesView.as_view()),
    path('players_challenges/<uuid:player_id>/', PlayerChallengesView.as_view()),
    path('team/<uuid:team_id>/', TeamDetailView.as_view(), name='team-detail'),
    path('teams/<uuid:team_id>/challenges/', ChallengeTeamsView.as_view()),
    path('create/', CreateChallengeAPIView.as_view(), name='create-challenge'),
    # GET  /teams/{team_id}/challenges/pending/
    path(
        "teams/<uuid:team_id>/challenges/pending/",
        PendingChallengeListView.as_view(),
        name="challenge-pending-list",
    ),

    # POST /challenges/{challenge_id}/reply/
    path(
        "challenges/<uuid:challenge_id>/reply/",
        ChallengeReplyView.as_view(),
        name="challenge-reply",
    ),
    
    # POST /challenges/{challenge_id}/cancel/
    path(
        "challenges/<uuid:challenge_id>/cancel/",
        ChallengeCancelView.as_view(),
        name="challenge-cancel",
    ),

    
    # GET  /teams/{team_id}/challenges/sent/
    path(
        "teams/<uuid:team_id>/challenges/sent/",
        SentChallengeListView.as_view(),
        name="challenge-sent-list",
    ),
    path('players/<uuid:player_id>/', PlayerProfileView.as_view(), name='player-profile'),
    path('challenge/<uuid:challenge_id>/', ChallengeDetailView.as_view(), name='challenge-detail'),

    path('', include(router.urls)),

]