from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import ClosedBookingCreateView, BookingViewSet, BookingPriceAPIView, BookingstatusAPIView, ClubOpeningPrices, EquipmentAvailabilityView

router = DefaultRouter()
router.register(r'', BookingViewSet, basename='booking')

urlpatterns = [
    path('calculate-price/', BookingPriceAPIView.as_view(), name='booking-price'),
    path('booking-status/', BookingstatusAPIView.as_view(), name='booking-status'),
    path('availabil-equipment/', EquipmentAvailabilityView.as_view(), name='availabil-equipment'),
    path('opening-prices/', ClubOpeningPrices.as_view(), name="opening-prices"),
    path('closed-booking/', ClosedBookingCreateView.as_view(), name='closed-booking-create'),

    
    path('', include(router.urls)),
    

]
