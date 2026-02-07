from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.decorators import api_view

from django.shortcuts import get_object_or_404
from dashboard_manage.models import Club
from  player_booking.models import Booking, BookingStatus, PayStatus
from .serializers import (
    BookingListSerializer,
    BookingDetailSerializer,
    BookingCreateSerializer,
    BookingUpdateSerializer,
    BookingRescheduleSerializer,
    BookingSlotFilterSerializer,
    BookingPriceRequestSerializer,
    BookingConvertStatusSerializer,
    BookingListPitchSerializer
)

# from .permissions import IsClubManager
from dashboard_booking.services.BookingService import BookingService
from dashboard_booking.services.PricingService import PricingService
from dashboard_booking.services.ClubTimeForOwnerService import ClubTimeForOwnerService


class BookingViewSet(viewsets.ModelViewSet):
    # permission_classes = [IsAuthenticated, IsClubManager]
    http_method_names = ['get', 'post', 'patch']

    
    def get_queryset(self):
        
        club_id = self.request.auth.get('club_id')
        if self.action == 'retrieve':
            return Booking.objects.filter(pitch__club_id=club_id).select_related('pitch', 'player')
        return Booking.objects.filter(pitch__club_id=club_id)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return BookingCreateSerializer
        # elif self.action in ['update', 'partial_update']:
        #     return BookingUpdateSerializer
        # elif self.action == 'by_day_pitch':
        #     return  BookingListSerializer
        elif self.action == 'convert_to_pending_player':
            return BookingRescheduleSerializer
        elif  self.action == 'convert_booking':
            return BookingConvertStatusSerializer
        elif  self.action == 'by_day_time_pitch':
            return BookingListPitchSerializer
        
        return BookingDetailSerializer
    
    """
    @action(detail=False, methods=['get'], url_path='by-day-pitch')
    def by_day_pitch(self, request):

        club_id = request.auth.get('club_id')
        date = request.query_params.get('date')
        pitch_id = request.query_params.get('pitch_id')
        
        if not date:
            return Response(
                {'error': 'date parameter is required (format: YYYY-MM-DD)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not pitch_id:
            return Response(
                {'error': 'pitch_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        bookings = Booking.objects.filter(
            pitch_id=pitch_id,
            pitch__club_id=club_id,
            date=date
        ).select_related('player').order_by('start_time')
        
        serializer = self.get_serializer(bookings, many=True)
        return Response(serializer.data)
    """


    @action(detail=False, methods=['get'], url_path='by-day-time-pitch')
    def by_day_time_pitch(self, request):
        """
        GET: List all bookings for a specific day, time and pitch
        """
        input_serializer = BookingSlotFilterSerializer(data=request.query_params)
        input_serializer.is_valid(raise_exception=True)
        
        params = input_serializer.validated_data
        
        club_id = request.auth.get('club_id')
        date = params['date']
        time_from = params.get('time_from', None)
        time_to = params.get('time_to', None)
        pitch_id = params['pitch_id']        
        
        bookings = Booking.objects.filter(
                    pitch_id=pitch_id,
                    pitch__club_id=club_id,
                    date=date
                ).select_related('player').order_by('start_time')
        

        if time_to and time_from:
            bookings=bookings.filter(
                start_time__lt=time_to, 
                end_time__gt=time_from
            )
            
        serializer = self.get_serializer(bookings, many=True)
        return Response(serializer.data)
    

    @action(detail=True, methods=['patch'], url_path='convert-booking')
    def convert_booking(self, request, pk=None):
        """
        PATCH: Convert booking to Pending_pay
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)


        try:
            booking = BookingService.owner_update_booking_status(pk, serializer.validated_data['status'], self.request.auth.get('club_id'))
            return Response({"status": f"Booking converted to {BookingStatus(serializer.validated_data['status']).label}"})
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    
    @action(detail=False, methods=['get'], url_path='show-convert-booking-status')
    def show_convert_booking_status(self, request, pk=None):

        return Response({
            BookingStatus.PENDING_MANAGER.name: [
                (BookingStatus.PENDING_PAY.name, BookingStatus.PENDING_PAY.value),
                (BookingStatus.REJECT.name, BookingStatus.REJECT.value),
                (BookingStatus.PENDING_PLAYER.name, BookingStatus.PENDING_PLAYER.value),
            ], 
            BookingStatus.COMPLETED.name:[
                (BookingStatus.DISPUTED.name, BookingStatus.DISPUTED.value),
                # (BookingStatus.NO_SHOW.name, BookingStatus.NO_SHOW.value),
                (BookingStatus.CANCELED.name, BookingStatus.CANCELED.value),
            ],
            BookingStatus.PENDING_PAY.name:[
                (BookingStatus.COMPLETED.name, BookingStatus.COMPLETED.value),
                (BookingStatus.CANCELED.name, BookingStatus.CANCELED.value),
                (BookingStatus.DISPUTED.name, BookingStatus.DISPUTED.value),
                (BookingStatus.NO_SHOW.name, BookingStatus.NO_SHOW.value),

            ]
            })
   
        
    @action(detail=True, methods=['patch'], url_path='convert-to-pending-player')
    def convert_to_pending_player(self, request, pk=None):
        """
        PATCH: Convert Pending_manager booking to Pending_player
        Creates notification for player with new schedule
        """
        booking = self.get_object()
        
        if booking.status != BookingStatus.PENDING_MANAGER:
            return Response(
                {'error': 'Only bookings with Pending_manager status can be converted to Pending_player'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        club_id = request.auth.get('club_id')
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            booking = BookingService.convert_to_pending_player(
                booking=booking,
                club=club_id,
                new_date=serializer.validated_data['new_date'],
                new_start_time=serializer.validated_data['new_start_time'],
                new_end_time=serializer.validated_data['new_end_time']
            )
            return Response({"status": "Booking converted to Pending player", "id": booking.id})
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )



class BookingPriceAPIView(APIView):
    
    def post(self, request):
        serializer = BookingPriceRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        pitch = serializer.validated_data['pitch']
        date = serializer.validated_data['date']
        start_time = serializer.validated_data['start_time']
        end_time = serializer.validated_data['end_time']
        
        club_id = self.request.auth.get('club_id')

        
        # Calculate price
        try:
            price = PricingService.calculate_final_price(
                pitch=pitch,
                club_id=club_id,
                date=date,
                start_time=start_time,
                end_time=end_time
            )
            
            return Response({
                'price': price
            }, status=status.HTTP_200_OK)
                
        except Exception as e:
            return Response({
                'error': 'Failed to calculate price',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class BookingstatusAPIView(APIView):
    def get(self, request):

    
        return Response({
            'PayStatus': {
                PayStatus.LATER.name:PayStatus.LATER.value,
                PayStatus.DEPOSIT.name:PayStatus.DEPOSIT.value
            },
            'BookingStatus':{
                BookingStatus.COMPLETED.name:BookingStatus.COMPLETED.value,
                BookingStatus.PENDING_PAY.name:BookingStatus.PENDING_PAY.value,
                BookingStatus.DISPUTED.name:BookingStatus.DISPUTED.value,
                BookingStatus.CANCELED.name:BookingStatus.CANCELED.value,
            }

        }, status=status.HTTP_200_OK)
    
        

@api_view(['GET'])
def ClubOpeningPrices(request):
    """
    GET: for list all opening time and the price for each pitch for club for next X days
    """

    
    opening_time_with_pitches_prices = ClubTimeForOwnerService.get_opening_time_with_pitches_prices(request.auth.get('club_id'), 10, request)
    return Response(opening_time_with_pitches_prices)