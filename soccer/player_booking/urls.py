from django.urls import path

from .views import EquipmentAvailabilityForUserView, ConsolidatedBookingListViewAlt, ActiveClubListAPIView, ClubOpeningPrices, BookingCreateForUser, ShowBookingDurationForClub


urlpatterns = [
    path('club-opening-prices/', ClubOpeningPrices, name="club-opening-prices"),
    path("booking-duration/<uuid:club_id>/", ShowBookingDurationForClub.as_view(), name="booking-duration"),
    path("consolidated-booking/", ConsolidatedBookingListViewAlt.as_view(), name="consolidated-booking"),
    path("clubs/", ActiveClubListAPIView.as_view(), name="active-club-list"),
    path("make-booking/", BookingCreateForUser.as_view(), name="make_booking_by_user"),
    path("availabil-equipment/", EquipmentAvailabilityForUserView.as_view(), name="availabil-equipment"),
]
