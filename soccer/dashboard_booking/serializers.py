from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import  BookingNotification
from  player_booking.models import Booking, BookingStatus
from dashboard_manage.models import Pitch
from dashboard_booking.services.PricingService import PricingService

User = get_user_model()


class BookingListSerializer(serializers.ModelSerializer):    
    player_name = serializers.CharField(source='player.username', read_only=True, allow_null=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'start_time', 'end_time', 'price', 'status','player_name'
        ]
class BookingDetailSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source='player.username', read_only=True, allow_null=True)
    pitch_name = serializers.CharField(source='pitch.name', read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'date', 'start_time', 'end_time', 'price', 'status',
            'created_at', 'updated_at', 'player_name', 'pitch_name'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BookingCreateSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)
    
    class Meta:
        model = Booking
        fields = ['pitch', 'date', 'start_time', 'end_time', 'username']
    
    def is_valid_username(self, value):

        if value:
            try:
                user = User.objects.get(username=value)
                return user
            except User.DoesNotExist:

                raise serializers.ValidationError(f"User with username '{value}' does not exist.")
        
    def validate_pitch(self, value):
        club_id = self.context['request'].auth.get('club_id')

        if str(value.club_id) != club_id:
            raise serializers.ValidationError("Pitch does not belong to your club.")
        return value
    
    def validate(self, attrs):
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError("End time must be after start time.")
        # Check for overlapping bookings
        pitch = attrs['pitch']
        date = attrs['date']
        start_time = attrs['start_time']
        end_time = attrs['end_time']
        
        overlapping = Booking.objects.filter(
            pitch=pitch,
            date=date,
            status__in=[
                BookingStatus.COMPLETED
            ]
        ).filter(
            start_time__lt=end_time,
            end_time__gt=start_time
        ).exists()
        
        if overlapping:
            raise serializers.ValidationError("This time slot overlaps with an existing booking.")
        
        return attrs
    
    def create(self, validated_data):
        username = validated_data.pop('username', None)
        user = self.is_valid_username(username) if username else None
        print(validated_data)
        price=PricingService.calculate_final_price(validated_data['pitch'], validated_data['pitch'].club_id, validated_data['date'], validated_data['start_time'], validated_data['end_time'])
        print(price)
        booking = Booking.objects.create(
            player=user,
            status =4,
            price=price,
            **validated_data
        )
        return booking


class BookingUpdateSerializer(serializers.ModelSerializer):    
    class Meta:
        model = Booking
        fields = ['date', 'start_time', 'end_time', 'price']
    
    def validate(self, attrs):
        start_time = attrs.get('start_time', self.instance.start_time)
        end_time = attrs.get('end_time', self.instance.end_time)
        
        if start_time >= end_time:
            raise serializers.ValidationError("End time must be after start time.")
        
        return attrs


class BookingRescheduleSerializer(serializers.Serializer):
    """Serializer for rescheduling booking (Pending_manager -> Pending_player)"""
    new_date = serializers.DateField()
    new_start_time = serializers.TimeField()
    new_end_time = serializers.TimeField()
    
    def validate(self, attrs):
        if attrs['new_start_time'] >= attrs['new_end_time']:
            raise serializers.ValidationError("End time must be after start time.")
        return attrs