from rest_framework import generics
from rest_framework.decorators import api_view
from rest_framework.response import Response
from soccer.enm import BOOKING_STATUS_DENIED
from rest_framework import status
from dashboard_booking.services.PricingService import PricingService
from urllib import request
from dashboard_manage.models import Club, BookingDuration, Pitch
from django.db.models import Prefetch
from management.models import Feature
from .serializers import BookingDetailSerializer, UserBookingSerializer, BookingPriceRequestForUserSerializer, EquipmentAvailabilityQueryForUserSerializer, ClubListSerializer, ClubIDFilterSerializer, BookingCreateForUserSerializer, ConsolidatedBookingQuerySerializer
from core.services.CouponService import CouponService
from .helper import haversine_distance
from .serializers import BookingPriceRequestForUserSerializer, CouponSerializer, EquipmentAvailabilityQueryForUserSerializer, ClubListSerializer, ClubIDFilterSerializer, BookingCreateForUserSerializer, ConsolidatedBookingQuerySerializer, PitchSearchResultSerializer, PitchSearchSerializer
from player_booking.services.ClubTimeService import ClubTimeService
from rest_framework.generics import get_object_or_404
from rest_framework.views import APIView
from .models import Booking, Coupon
from .services.ClubInfoService import ClubInfoService
from dashboard_booking.services.EquipmentBookingService import EquipmentBookingService
from django.conf import settings


from .services.BookingHistoryService import UserBookingService 


from .services.booking_detail_service import UserBookingDetailService


class UserBookingDetailView(generics.RetrieveAPIView):
    serializer_class   = BookingDetailSerializer

    def get_object(self):
        return UserBookingDetailService.get_booking_detail(
            booking_id=self.kwargs['booking_id'],
            user_id=self.request.user.id,
        )
    


class UserBookingListView(generics.ListAPIView):
    serializer_class   = UserBookingSerializer

    def get_queryset(self):
        return UserBookingService.get_user_bookings(self.request.user.id)



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

class CouponCreateView(APIView):
    # permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = CouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        club = None
        if user.role == 2:  # ← replace 2 with your actual owner role value
            try:
                club = Club.objects.get(manager=user)
            except Club.DoesNotExist:
                return Response(
                    {'error': 'لم يتم العثور على نادي مرتبط بهذا المستخدم.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        coupon = serializer.save()
        coupon = serializer.save(club=club)
        return Response(CouponSerializer(coupon).data, status=status.HTTP_201_CREATED)

class ShowBookingDurationForClub(APIView):
    
    def get(self, request, club_id):
        duration = BookingDuration.objects.values("duration").filter(club_id=club_id)

        return Response(duration)

class PitchSearchView(APIView):

    def post(self, request):
        serializer = PitchSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        date = serializer.validated_data['date']
        start_time = serializer.validated_data['start_time']
        end_time = serializer.validated_data['end_time']
        user_lat = serializer.validated_data['user_latitude']
        user_lon = serializer.validated_data['user_longitude']
        pitch_type = serializer.validated_data.get('type', None)
        size_high = serializer.validated_data.get('size_high', None)
        size_width = serializer.validated_data.get('size_width', None)

        # Get booked pitch ids that overlap with requested time
        booked_pitch_ids = Booking.objects.filter(
            date=date,
            status__in=BOOKING_STATUS_DENIED,  # your existing constant
            start_time__lt=end_time,
            end_time__gt=start_time
        ).values_list('pitch_id', flat=True)

        # Get available pitches
        pitches = Pitch.objects.filter(
            is_active=True,
            is_deteted=False,
            club__is_active=True,
        ).exclude(
            id__in=booked_pitch_ids
        ).select_related('club')

        # Optional filters
        if pitch_type:
            pitches = pitches.filter(type=pitch_type)
        if size_high:
            pitches = pitches.filter(size_high=size_high)
        if size_width:
            pitches = pitches.filter(size_width=size_width)

        # Calculate distance for each pitch and attach it
        results = []
        for pitch in pitches:
            distance = haversine_distance(
                user_lat, user_lon,
                pitch.club.latitude, pitch.club.longitude
            )
            pitch.distance_km = distance
            results.append(pitch)

        # Sort by nearest to farthest
        results.sort(key=lambda p: p.distance_km)

        response_serializer = PitchSearchResultSerializer(
            results,
            many=True,
            context={'request': request}
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)

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
        coupon_code = serializer.validated_data.get('coupon_code', None)
        response = dict()
        try:
            pitchprice = PricingService.calculate_final_price(
                pitch=pitch,
                club_id=club_id,
                date=date,
                start_time=start_time,
                end_time=end_time
            )
            price=0

            if equipments:
                response = EquipmentBookingService.Get_Equipment_Price(club_id, equipments, start_time, end_time)
                price = price + response['equipments_price']

            total_price = price + pitchprice
            response['pitch_price'] = pitchprice
            response['discount'] = 0
            response['coupon_applied'] = False
            response['price'] = total_price
            if coupon_code:
                request_user = request.user if request.user.is_authenticated else None
                coupon_result = CouponService.apply_coupon(total_price, coupon_code,user=request_user, club_id=club_id)
                coupon_result.pop('coupon', None)
                response.update(coupon_result)


            
            return Response(response, status=status.HTTP_200_OK)
                
        except Exception as e:
            return Response({
                'error': 'فشل حساب السعر. يرجى التحقق من البيانات المدخلة والمحاولة مرة أخرى.',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
