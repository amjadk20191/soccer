from django.urls import path

from .views import (UserBookingListView, BookingPriceForUserAPIView, 
                    EquipmentAvailabilityForUserView, ConsolidatedBookingListViewAlt, 
                    ActiveClubListAPIView, ClubOpeningPrices, BookingCreateForUser, 
                    ShowBookingDurationForClub, UserBookingDetailView)
from .views import (BookingPriceForUserAPIView, EquipmentAvailabilityForUserView, 
                    ConsolidatedBookingListViewAlt, ActiveClubListAPIView, 
                    ClubOpeningPrices, BookingCreateForUser, ShowBookingDurationForClub, 
                    CouponCreateView, PitchSearchView, BookingStatusListView)


urlpatterns = [
    path('club-opening-prices/', ClubOpeningPrices, name="club-opening-prices"),
    path("booking-duration/<uuid:club_id>/", ShowBookingDurationForClub.as_view(), name="booking-duration"),
    path("consolidated-booking/", ConsolidatedBookingListViewAlt.as_view(), name="consolidated-booking"),
    path("clubs/", ActiveClubListAPIView.as_view(), name="active-club-list"),
    path("make-booking/", BookingCreateForUser.as_view(), name="make_booking_by_user"),
    path("availabil-equipment/", EquipmentAvailabilityForUserView.as_view(), name="availabil-equipment"),
    path('calculate-price/', BookingPriceForUserAPIView.as_view(), name='booking-price'),
    path('mybooking/', UserBookingListView.as_view(), name='user-bookings'),
    path('my/<uuid:booking_id>/', UserBookingDetailView.as_view(), name='user-booking-detail'),
    path('booking-status/', BookingStatusListView.as_view(), name='Booking Status'),


    path('add-coupon/', CouponCreateView.as_view(), name='add-coupon'),
    path('pitches/search/', PitchSearchView.as_view(), name='pitch-search'),
]
