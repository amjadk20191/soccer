from rest_framework import generics
from rest_framework.decorators import api_view
from rest_framework.response import Response

from dashboard_manage.models import Club
from django.db.models import Prefetch
from management.models import Feature
from .serializers import ClubListSerializer, ClubIDFilterSerializer
from player_booking.services.ClubTimeService import ClubTimeService


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
    
    
    opening_time_with_pitches_prices = ClubTimeService.get_opening_time_with_pitches_prices(params['club_id'], 10)
    return Response(opening_time_with_pitches_prices)