from django.urls import path

from .views import ActiveClubListAPIView, ClubOpeningPrices


urlpatterns = [
    path("clubs/", ActiveClubListAPIView.as_view(), name="active-club-list"),
    path('club-opening-prices/', ClubOpeningPrices, name="club-opening-prices"),
]
