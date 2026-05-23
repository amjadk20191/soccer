from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ClubPayoutSummaryView, ClubRevenueView, RecordPayoutView


router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
    path("club-revenue/", ClubRevenueView.as_view(), name="club-revenue"),
    path('club-payouts/',        ClubPayoutSummaryView.as_view()),
    # path('club-payouts/record/', RecordPayoutView.as_view()),
]