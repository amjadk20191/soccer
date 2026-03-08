from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChallengeTeamsView, CreateChallengeAPIView

router = DefaultRouter()

urlpatterns = [
    path('teams/<uuid:team_id>/challenges/', ChallengeTeamsView.as_view()),
    path('create/', CreateChallengeAPIView.as_view(), name='create-challenge'),
    path('', include(router.urls)),

]