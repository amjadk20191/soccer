from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import BookingViewSet, BookingPriceAPIView, BookingstatusAPIView, ClubOpeningPrices

router = DefaultRouter()
router.register(r'', BookingViewSet, basename='booking')

urlpatterns = [
    path('calculate-price/', BookingPriceAPIView.as_view(), name='booking-price'),
    path('booking-status/', BookingstatusAPIView.as_view(), name='booking-status'),
    path('opening-prices/', ClubOpeningPrices, name="opening-prices"),

    
    path('', include(router.urls)),
    

]
