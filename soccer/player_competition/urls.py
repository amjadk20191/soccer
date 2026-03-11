from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SentChallengeListView, ChallengeCancelView, ChallengeTeamsView, CreateChallengeAPIView, PendingChallengeListView, ChallengeReplyView

router = DefaultRouter()

urlpatterns = [
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
    path('', include(router.urls)),

]