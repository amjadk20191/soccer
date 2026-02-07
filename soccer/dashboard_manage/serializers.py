from rest_framework import serializers
from .models import Club, ClubPricing, Pitch

class ClubManagerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = [
            'id',  'name', 'description', 'address', 
            'latitude', 'longitude', 'open_time', 'close_time', 
            'working_days', 'logo', 'rating_avg', 'rating_count', 
            'flexible_reservation','is_active'
        ]
        read_only_fields = [
            'id', 
            'name', 
            'latitude', 
            'longitude', 
            'rating_avg', 
            'rating_count',
            'logo'
        ]

    def get_logo(self, obj):
        if not obj.logo:
            return None
        
        request = self.context.get('request')
        return request.build_absolute_uri(obj.logo.url) if request else obj.logo.url
    def validate(self, attrs):
    
        open_time = attrs.get('open_time', self.instance.open_time)
        close_time = attrs.get('close_time', self.instance.close_time)
        
        if open_time and close_time:
            if close_time <= open_time:
                raise serializers.ValidationError({
                    'error': 'Close time must be after open time.'
                })
        
        return attrs

#for 'day_of_week'
class WeekdayPricingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClubPricing

        fields = ['id', 'day_of_week', 'start_time', 'end_time', 'percent']
        read_only_fields = ['id']

    def validate(self, attrs):
        request = self.context.get('request')
            
        club_id = request.auth.payload.get('club_id')
        
        day_of_week= attrs.get('day_of_week',None)
        if  day_of_week is None:
            raise serializers.ValidationError({"day_of_week": "This field is required."})
        
        if not day_of_week in [0, 1, 2, 3, 4, 5, 6]:
            raise serializers.ValidationError({"day_of_week": "should be one of 0, 1, 2, 3, 4, 5, 6."})
        
        open_time = attrs.get('start_time')
        close_time = attrs.get('end_time')
        if open_time >= close_time:
            raise serializers.ValidationError({"end_time": "End time must be after start time."})

        weekday=ClubPricing.objects.filter(club_id=club_id,day_of_week=attrs.get('day_of_week')).exists()

        if weekday:
            raise serializers.ValidationError({"error": "this weekday already exist."})
        
        is_day_off = Club.objects.values('working_days').filter(id=club_id).first()
        if not is_day_off['working_days'][str(day_of_week)]:
            raise serializers.ValidationError({"error": "this weekday is an off day."})

        return attrs

    def create(self, validated_data):

        validated_data['type'] = 1
        validated_data['date'] = None
        return super().create(validated_data)


#for 'date'
class DatePricingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClubPricing
        fields = ['id', 'date', 'start_time', 'end_time', 'percent']
        read_only_fields = ['id']

    def validate(self, attrs):
        request = self.context.get('request')
            
        if request and hasattr(request, 'auth') and request.auth:
            club_id = request.auth.payload.get('club_id')

        if attrs.get('date') is None:
            raise serializers.ValidationError({"date": "This field is required."})
       
        open_time = attrs.get('start_time')
        close_time = attrs.get('end_time')
        if open_time >= close_time:
            raise serializers.ValidationError({"error": "End time must be after start time."})
        
        date=ClubPricing.objects.filter(club_id=club_id,date=attrs.get('date')).exists()

        if date:
            raise serializers.ValidationError({"error": "this date already exist."})

        return attrs

    def create(self, validated_data):

        validated_data['type'] = 2
        validated_data['day_of_week'] = None
        return super().create(validated_data)
    

class PitchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pitch
        fields = [
            'id', 'name', 'image', 'type', 'size_high', 'size_width', 
            'price_first', 'price_second', 'time_interval', 'is_active'
        ]
        read_only_fields = ['id', 'is_active']



class PitchListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pitch
        fields = [
            'id', 'name', 'image', 'is_active'
        ]
        read_only_fields = ['id', 'is_active']


class PitchActivationSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(required=True)