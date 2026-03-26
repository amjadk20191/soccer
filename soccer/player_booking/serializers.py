from rest_framework import serializers

from dashboard_manage.models import Club, ClubPricing, Pitch
from management.models import Feature
from soccer.enm import BOOKING_STATUS_DENIED
from  player_booking.models import Booking, BookingStatus, PayStatus, BookingEquipment
from django.db import transaction
from django.conf import settings
from datetime import date, timedelta

from dashboard_booking.services.PricingService import PricingService
from dashboard_booking.services.EquipmentBookingService import EquipmentBookingService

from datetime import datetime


class ConsolidatedBookingQuerySerializer(serializers.Serializer):
    """Validates query parameters for consolidated booking endpoint"""
    
    pitch = serializers.UUIDField(required=True)
    club = serializers.UUIDField(required=True)
    date = serializers.DateField(required=True, format='%Y-%m-%d')
    
    def validate_date(self, value):
        """
        Validate that date is not in the past
        Optional: Remove if you want to allow past dates
        """
        if value < datetime.now().date():
            raise serializers.ValidationError("Date cannot be in the past")
        return value

class EquipmentAvailabilityQueryForUserSerializer(serializers.Serializer):
    date = serializers.DateField(required=True)
    start_time = serializers.TimeField(required=True)
    end_time = serializers.TimeField(required=True)
    club = serializers.UUIDField()
    
    def validate(self, data):
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError({
                "time": "start_time must be before end_time"
            })
        return data

class TagSerializer(serializers.Serializer):
    name = serializers.CharField()
    logo = serializers.ImageField()


class ClubListSerializer(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()

    class Meta:
        model = Club
        fields = [
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
            "tags",
        ]

    def get_tags(self, obj):
        # Fast path: ActiveClubListAPIView prefetches to obj.active_features
        features = getattr(obj, "active_features", None)
        if features is None:
            # Fallback (still correct, but slower)
            features = (
                Feature.objects.select_related("tag")
                .filter(club=obj, is_active=True)
                .only("tag__name", "tag__logo")
            )
        return TagSerializer([f.tag for f in features], many=True, context=self.context).data


class ClubIDFilterSerializer(serializers.Serializer):
    club_id = serializers.UUIDField()
   
    # def validate(self, data):

    #     if data.get('from_time') and data.get('to_time'):
    #         if data['from_time'] >= data['to_time']:
    #             raise serializers.ValidationError("from_time must be before to_time")
    #     return data


class EquipmentBookingForUserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)

class BookingCreateForUserSerializer(serializers.ModelSerializer):
    equipments = EquipmentBookingForUserSerializer(many=True, required=False)
    club = serializers.UUIDField()
    
    class Meta:
        model = Booking
        fields = ['club', 'pitch', 'date', 'start_time', 'end_time',  'price', 'final_price', 'equipments']
        extra_kwargs = {
            'price': {
                'read_only':True
            },
            'final_price': {
                'read_only':True
            }
        }
        
    def validate_date(self, value):
        today = date.today()
        if not (today + timedelta(days=settings.MIN_NUM_DAY_BEFORE_BOOKING) <= value <= today + timedelta(days=settings.MAX_NUM_DAY_BEFORE_BOOKING)):
            raise serializers.ValidationError(f'Date must be between {settings.MIN_NUM_DAY_BEFORE_BOOKING} and {settings.MAX_NUM_DAY_BEFORE_BOOKING} days from today.')
        return value
    
    def validate(self, attrs):
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError("End time must be after start time.")
                
        day_number = (attrs['date'].weekday() + 2) % 7 
        print(f"Day Number: {day_number}")
        print(attrs["club"])
        print(type(attrs["club"]))
        is_date_off = ClubPricing.objects.filter(club_id=attrs["club"], type=2, date=attrs["date"]).exists()
        is_day_off = Club.objects.values('working_days').filter(id=attrs["club"], is_active=True).first()
        if not is_day_off:
            raise serializers.ValidationError({"error": "club not Active"})

        print(is_day_off)
        if not (is_day_off['working_days'][str(day_number)] or is_date_off):
            raise serializers.ValidationError({"error": "this weekday is an off day."})
        print("//////////////////////////")
        pitch_exist = attrs['pitch'].club_id!=attrs['club'] or attrs['pitch'].is_deteted==True or attrs['pitch'].is_active==False
        print(pitch_exist)
        if pitch_exist:
            raise serializers.ValidationError({"error": "the pitch is not for club"})
        print("//////////////////////////")


        # Check for overlapping bookings
        pitch = attrs['pitch']
        date = attrs['date']
        start_time = attrs['start_time']
        end_time = attrs['end_time']
        
        overlapping = Booking.objects.filter(
            pitch=pitch,
            date=date,
            status__in=BOOKING_STATUS_DENIED
        ).filter(
            start_time__lt=end_time,
            end_time__gt=start_time
        ).exists()
        
        if overlapping:
            raise serializers.ValidationError("This time slot overlaps with an existing booking.")
        
        #with the user himself
        player = self.context['request'].user
        overlapping = Booking.objects.filter(
            player=player,
            date=date,
            status__in= [
            BookingStatus.PENDING_PAY.value,
            BookingStatus.COMPLETED.value,
            BookingStatus.PENDING_PLAYER.value,
            BookingStatus.PENDING_MANAGER.value,
        ]
        ).filter(
            start_time__lt=end_time,
            end_time__gt=start_time
        ).exists()
        
        if overlapping:
            raise serializers.ValidationError("This time slot overlaps with an existing booking.")
        
        
        return attrs
    
    def create(self, validated_data):
        club_id = validated_data.pop('club')
        user_id = self.context['request'].auth.get('user_id')
        price = PricingService.calculate_final_price(validated_data['pitch'], club_id, validated_data['date'], validated_data['start_time'], validated_data['end_time'])
        equipments = validated_data.pop("equipments", [])

    
        with transaction.atomic():
            booking = Booking.objects.create(
                club_id=club_id,
                player_id=user_id,
                price=price,
                final_price=price,
                **validated_data)
            if equipments:
                equipments = EquipmentBookingService.Create_Equipment_Booking(club_id, booking, equipments, validated_data['start_time'],  validated_data['end_time'])
        
        return booking

class EquipmentBookingSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)

class BookingPriceRequestForUserSerializer(serializers.ModelSerializer):
    equipments = EquipmentBookingSerializer(many=True, required=False)

    class Meta:
        model = Booking
        fields = ['pitch', 'date', 'start_time', 'end_time', 'equipments', 'club']
    
    def validate(self, attrs):
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError("End time must be after start time.")
        return attrs
        