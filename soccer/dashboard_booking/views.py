from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from dashboard_manage.models import Club
from  player_booking.models import Booking, BookingStatus
from .serializers import (
    BookingListSerializer,
    BookingDetailSerializer,
    BookingCreateSerializer,
    BookingUpdateSerializer,
    BookingRescheduleSerializer,
    BookingSlotFilterSerializer
)
# from .permissions import IsClubManager
from dashboard_booking.services.BookingService import BookingService


class BookingViewSet(viewsets.ModelViewSet):

    # permission_classes = [IsAuthenticated, IsClubManager]
    http_method_names = ['get', 'post', 'patch']

    
    def get_queryset(self):
        
        club_id = self.request.auth.get('club_id')
        if self.request.method == 'GET':
            return Booking.objects.filter(pitch__club_id=club_id).select_related('pitch', 'player')
        return Booking.objects.filter(pitch__club_id=club_id)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return BookingCreateSerializer
        # elif self.action in ['update', 'partial_update']:
        #     return BookingUpdateSerializer
        elif self.action == 'by_day_pitch':
            return  BookingListSerializer
        elif self.action == 'convert_to_pending_player':
            return BookingRescheduleSerializer
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
    

    @action(detail=True, methods=['patch'], url_path='convert-to-pending-pay')
    def convert_to_pending_pay(self, request, pk=None):
        """
        PATCH: Convert Pending_manager booking to Pending_pay
        """
        booking = self.get_object()
        
        if booking.status != BookingStatus.PENDING_MANAGER:
            return Response(
                {'error': 'Only bookings with Pending_manager status can be converted to Pending_pay'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            booking = BookingService.convert_to_pending_pay(booking)
            return Response({"status": "Booking converted to Pending Pay", "id": booking.id})
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
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
    
    @action(detail=True, methods=['patch'], url_path='reject')
    def reject(self, request, pk=None):
        """
        PATCH: Reject booking (Pending_manager or Pending_player -> Reject)
        """
        booking = self.get_object()
        
        if booking.status not in [BookingStatus.PENDING_MANAGER, BookingStatus.PENDING_PLAYER]:
            return Response(
                {'error': 'Only bookings with Pending_manager or Pending_player status can be rejected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            booking = BookingService.reject_booking(booking)
            return Response({"status": "Booking converted to reject", "id": booking.id})
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )