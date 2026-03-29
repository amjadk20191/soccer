from rest_framework import generics
from rest_framework.decorators import api_view
from rest_framework.response import Response
from soccer.enm import BOOKING_STATUS_DENIED
from rest_framework import status
from dashboard_booking.services.PricingService import PricingService

from dashboard_manage.models import Club, BookingDuration
from django.db.models import Prefetch
from management.models import Feature
from .serializers import BookingPriceRequestForUserSerializer, EquipmentAvailabilityQueryForUserSerializer, ClubListSerializer, ClubIDFilterSerializer, BookingCreateForUserSerializer, ConsolidatedBookingQuerySerializer
from player_booking.services.ClubTimeService import ClubTimeService
from rest_framework.generics import get_object_or_404
from rest_framework.views import APIView
from .models import Booking
from .services.ClubInfoService import ClubInfoService
from dashboard_booking.services.EquipmentBookingService import EquipmentBookingService
from django.conf import settings


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
    
    
    opening_time_with_pitches_prices = ClubTimeService.get_opening_time_with_pitches_prices(params['club_id'], settings.MAX_NUM_DAY_BEFORE_BOOKING, request)
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
    



class EquipmentAvailabilityForUserView(APIView):
    
    def get(self, request):
        query_serializer = EquipmentAvailabilityQueryForUserSerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        
        # Get validated data
        validated_data = query_serializer.validated_data
        booking_date = validated_data['date']
        start_time = validated_data['start_time']
        end_time = validated_data['end_time']
        
        club_id = validated_data['club']
        try:
            available_equipments = EquipmentBookingService.Get_equipment_quantities_for_time(
                club_id=club_id,
                booking_date=booking_date,
                start_time=start_time,
                end_time=end_time,
                request=request
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response(available_equipments, status=status.HTTP_200_OK)
    


    
class BookingPriceForUserAPIView(APIView):
    
    def post(self, request):
        serializer = BookingPriceRequestForUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        pitch = serializer.validated_data['pitch']
        date = serializer.validated_data['date']
        start_time = serializer.validated_data['start_time']
        end_time = serializer.validated_data['end_time']
        equipments = serializer.validated_data.get('equipments', None)
    
        club_id = serializer.validated_data['club']


        response = dict()
        # Calculate price
        try:
            price = PricingService.calculate_final_price(
                pitch=pitch,
                club_id=club_id,
                date=date,
                start_time=start_time,
                end_time=end_time
            )

            if equipments:
                response = EquipmentBookingService.Get_Equipment_Price(club_id, equipments, start_time, end_time)
                response['price'] = price + response['equipments_price']

            response['pitch_price'] = price
            print(response)


            return Response(dict(response), status=status.HTTP_200_OK)
                
        except Exception as e:
            return Response({
                'error': 'فشل حساب السعر. يرجى التحقق من البيانات المدخلة والمحاولة مرة أخرى.',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
