from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import  BookingNotification
from  player_booking.models import Booking, BookingStatus
from dashboard_manage.models import Pitch
from dashboard_booking.services.PricingService import PricingService

User = get_user_model()


class BookingListSerializer(serializers.ModelSerializer):    
    player_name = serializers.CharField(source='player.username', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'start_time', 'end_time', 'price', 'status_display', 'player_name'
        ]

class BookingDetailSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source='player.username', read_only=True, allow_null=True)
    pitch_name = serializers.CharField(source='pitch.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'date', 'start_time', 'end_time', 'price', 'status_display',
            'created_at', 'updated_at', 'player_name', 'pitch_name'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class BookingCreateSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)
    
    class Meta:
        model = Booking
        fields = ['pitch', 'date', 'start_time', 'end_time', 'username', 'phone', 'note_owner', 'payment_status', 'status', 'deposit']
    
    def is_valid_username(self, value):

        if value:
            try:
                user = User.objects.get(username=value, role=1)
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
        
        # if the payment_status is 2 "Deposit" then deposit field should be grater than 0
        if attrs['payment_status'] == 2 and attrs.get('deposit', 0) <= 0:
            raise serializers.ValidationError("deposit is required and should be bigger than 0.")          
        
        # Check for overlapping bookings
        pitch = attrs['pitch']
        date = attrs['date']
        start_time = attrs['start_time']
        end_time = attrs['end_time']
        
        overlapping = Booking.objects.filter(
            pitch=pitch,
            date=date
        ).filter(
            start_time__lt=end_time,
            end_time__gt=start_time
        ).exists()
        
        if overlapping:
            raise serializers.ValidationError("This time slot overlaps with an existing booking.")
        
        return attrs
    
    def create(self, validated_data:dict):
        username = validated_data.pop('username', None)
        user = self.is_valid_username(username) if username else None
        price=PricingService.calculate_final_price(validated_data['pitch'], validated_data['pitch'].club_id, validated_data['date'], validated_data['start_time'], validated_data['end_time'])
        
        if validated_data['status'] == 4:
            validated_data.pop('payment_status')  
        if validated_data.get('payment_status',2) != 2:
            validated_data.pop('deposit', None)
        
        booking = Booking.objects.create(
            player=user,
            status=4,
            price=price,
            by_owner=True,
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
    
class BookingSlotFilterSerializer(serializers.Serializer):
    date = serializers.DateField(format='%Y-%m-%d')
    pitch_id = serializers.UUIDField()
    time_from = serializers.TimeField(format='%H:%M', required=False)
    time_to = serializers.TimeField(format='%H:%M', required=False)
   
    def validate(self, data):

        if data.get('from_time') and data.get('to_time'):
            if data['from_time'] >= data['to_time']:
                raise serializers.ValidationError("from_time must be before to_time")
        return data