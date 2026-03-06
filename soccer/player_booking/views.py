from rest_framework import generics
from rest_framework.decorators import api_view
from rest_framework.response import Response
from soccer.enm import BOOKING_STATUS_DENIED

from dashboard_manage.models import Club, BookingDuration
from django.db.models import Prefetch
from management.models import Feature
from .serializers import ClubListSerializer, ClubIDFilterSerializer, BookingCreateForUserSerializer, ConsolidatedBookingQuerySerializer
from player_booking.services.ClubTimeService import ClubTimeService
from rest_framework.generics import get_object_or_404
from rest_framework.views import APIView
from .models import Booking
from .services.ClubInfoService import ClubInfoService


class ActiveClubListAPIView(generics.ListAPIView):
    """
    List all active clubs with their basic info and tags.
    """

    serializer_class = ClubListSerializer

    def get_queryset(self):
        # Only active clubs
        return (
            Club.objects.filter(is_active=True)
            .prefetch_related(
                Prefetch(
                    "feature_set",
                    queryset=Feature.objects.filter(is_active=True)
                    .select_related("tag")
                    .only("club_id", "tag__name", "tag__logo"),
                    to_attr="active_features",
                )
            )
            .only(
                "id",
                "name",
                "description",
                "address",
                "latitude",
                "longitude",
                "open_time",
                "close_time",
                "logo",
                "rating_avg",
                "rating_count",
                "flexible_reservation",
            )
        )

@api_view(['GET'])
def ClubOpeningPrices(request):
    """
    GET: for list all opening time and the price for each pitch for club for next X days
    """

    input_serializer = ClubIDFilterSerializer(data=request.query_params)
    input_serializer.is_valid(raise_exception=True)
    params = input_serializer.validated_data
    
    
    opening_time_with_pitches_prices = ClubTimeService.get_opening_time_with_pitches_prices(params['club_id'], 10, request)
    return Response(opening_time_with_pitches_prices)





class BookingCreateForUser(generics.CreateAPIView):
    # permission_classes = [IsAuthenticated, IsClubManager]

    serializer_class = BookingCreateForUserSerializer


class ShowBookingDurationForClub(APIView):
    
    def get(self, request, club_id):
        duration = BookingDuration.objects.values("duration").filter(club_id=club_id)

        return Response(duration)



class ConsolidatedBookingListViewAlt(APIView):
    """Alternative approach using helper method"""
    
    serializer_class = ConsolidatedBookingQuerySerializer
    
    def get(self, request):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data=serializer.validated_data
        times = ClubInfoService.get_free_booking_time(validated_data['pitch'], validated_data['club'], validated_data['date'])
        return Response(times)


    def get_serializer(self, *args, **kwargs):
        """Helper method to instantiate serializer"""
        return self.serializer_class(*args, **kwargs)
    
   