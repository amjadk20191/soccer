from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (ClubEquipmentGenericsList, ClubManagerView, WeekdayPricingViewSet, DatePricingViewSet, PitchViewSet, EquipmentGenericsList,
                    RevenueReportView, BookingCountsReportView, HourlyUtilisationReportView, 
                    EquipmentSalesReportView, BookingDurationViewSet,  GetPitchesTypesView)
router = DefaultRouter()

router.register(r'pricing/weekday', WeekdayPricingViewSet, basename='pricing-weekday')
router.register(r'pricing/date', DatePricingViewSet, basename='pricing-date')
router.register(r'pitches', PitchViewSet, basename='pitch')
router.register(r'equipment', ClubEquipmentGenericsList, basename='equipment')
router.register(r'booking-duration', BookingDurationViewSet, basename='booking-duration')

urlpatterns = [
    path('manager-club/', ClubManagerView.as_view(), name='manager-club'),
    path('equipment-list/', EquipmentGenericsList.as_view(), name='equipment-list'),
    path("dashboard/revenue/",   RevenueReportView.as_view()),
    path("dashboard/bookings/",  BookingCountsReportView.as_view()),
    path("dashboard/hourly/",    HourlyUtilisationReportView.as_view()),
    path("dashboard/equipment/", EquipmentSalesReportView.as_view()),
    path('get-pitch-types/', GetPitchesTypesView.as_view(), name='get-pitch-types'),
    path('', include(router.urls)),


]