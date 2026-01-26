from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ClubManagerView, WeekdayPricingViewSet, DatePricingViewSet, PitchViewSet

router = DefaultRouter()

router.register(r'pricing/weekday', WeekdayPricingViewSet, basename='pricing-weekday')
router.register(r'pricing/date', DatePricingViewSet, basename='pricing-date')
router.register(r'pitches', PitchViewSet, basename='pitch')

urlpatterns = [
    path('', include(router.urls)),
    path('manager-club/', ClubManagerView.as_view(), name='manager-club'),

]