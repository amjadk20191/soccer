from rest_framework import viewsets, mixins, permissions, parsers, exceptions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from rest_framework.views import APIView
from django.utils import timezone
from django.db import transaction

from .models import Club, ClubPricing, Pitch
from .serializers import ClubManagerSerializer, WeekdayPricingSerializer, DatePricingSerializer, PitchSerializer, PitchListSerializer, PitchActivationSerializer

class ClubManagerView(APIView):


    serializer_class = ClubManagerSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_object(self):
        club_id = self.request.auth.get('club_id')

        obj = get_object_or_404(
            Club, 
            pk=club_id, 
            manager=self.request.user
        )
        return obj
    def get(self, request):
        """Retrieve club data"""
        club = self.get_object()
        serializer = ClubManagerSerializer(club, context={'request': request})
        return Response(serializer.data)
    
    def put(self, request):
        """Full update club data"""
        club = self.get_object()
        serializer = ClubManagerSerializer(club, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request):
        """Partial update club data"""
        club = self.get_object()
        import json

        working_days=request.data.get('working_days',None)
        print(working_days)
        if working_days:
            working_days = json.loads(working_days)
            false_days = [int(day) for day, is_active in working_days.items() if is_active is False]
            day_off = ClubPricing.objects.filter(club_id=club.id, day_of_week__in=false_days).exists()
            if day_off:
                return Response({"error":"can not make the updated day off because there is ClubPricing active "}, status=status.HTTP_400_BAD_REQUEST)

        
        serializer = ClubManagerSerializer(club, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class _BasePricingViewSet(viewsets.ModelViewSet):

    def get_club(self):
        try:
            return self.request.user.club 
        except AttributeError:
            raise exceptions.PermissionDenied("User is not associated with a club.")

    def perform_create(self, serializer):
        serializer.save(club=self.get_club())

class WeekdayPricingViewSet(_BasePricingViewSet):
    serializer_class = WeekdayPricingSerializer

    def get_queryset(self):
        return ClubPricing.objects.filter(
            club=self.get_club(), 
            type=1,
        )

class DatePricingViewSet(_BasePricingViewSet):
    serializer_class = DatePricingSerializer

    def get_queryset(self):
        now = timezone.now()
        current_date = now.date()
        return ClubPricing.objects.filter(
            club=self.get_club(), 
            type=2,
            date__gte=current_date

        )

class PitchViewSet(viewsets.ModelViewSet):
    # permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        club_id = getattr(user, 'club_id', None)
        
        if not club_id and self.request.auth:
             club_id = self.request.auth.get('club_id')

        return Pitch.objects.filter(club_id=club_id)

    def get_serializer_class(self):
        if self.action == 'list':
            return PitchListSerializer
        if self.action == 'set_active':
            return PitchActivationSerializer
        return PitchSerializer

    def perform_create(self, serializer):
        user = self.request.user
        club_id = getattr(user, 'club_id', None)
        if not club_id and self.request.auth:
             club_id = self.request.auth.get('club_id')
        serializer.save(club_id=club_id)
    
    @action(detail=True, methods=['patch'], url_path='set-active')
    def set_active(self, request, pk):
        serializer = PitchActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            updated_count = self.get_queryset().filter(pk=pk).update(
                is_active=serializer.validated_data['is_active'],
                updated_at=timezone.now()
            )
           
            if not updated_count:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

            if not self.get_queryset().filter(is_active=True).exists():
                club_id = self.request.auth.get('club_id')
                Club.objects.filter(id=club_id).update(is_active=False,
                                                    updated_at=timezone.now())
      
        return Response(serializer.validated_data, status=status.HTTP_200_OK)