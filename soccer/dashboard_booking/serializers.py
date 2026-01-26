from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import  BookingNotification
from  player_booking.models import Booking, BookingStatus
from dashboard_manage.models import Pitch


User = get_user_model()


class BookingListSerializer(serializers.ModelSerializer):
    """Minimal serializer for listing bookings by day and pitch"""
    
    class Meta:
        model = Booking
        fields = ['start_time', 'end_time', 'price', 'status']


class BookingDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single booking view"""
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
    """Serializer for creating bookings"""
    username = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)
    
    class Meta:
        model = Booking
        fields = ['pitch', 'date', 'start_time', 'end_time', 'price', 'username']
    
    def validate_username(self, value):
        """Validate and get user from username"""
        if value:
            try:
                user = User.objects.get(username=value)
                return user
            except User.DoesNotExist:
                raise serializers.ValidationError(f"User with username '{value}' does not exist.")
        return None
    
    def validate_pitch(self, value):
        """Ensure pitch belongs to manager's club"""
        club_id = self.context['request'].auth.get('club_id')
        if value.club_id != club_id:
            raise serializers.ValidationError("Pitch does not belong to your club.")
        return value
    
    def validate(self, attrs):
        """Validate booking time slot"""
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
        user = self.validate_username(username) if username else None
        
        booking = Booking.objects.create(
            player=user,
            **validated_data
        )
        return booking


class BookingUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating booking fields"""
    
    class Meta:
        model = Booking
        fields = ['date', 'start_time', 'end_time', 'price']
    
    def validate(self, attrs):
        """Validate booking time slot"""
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