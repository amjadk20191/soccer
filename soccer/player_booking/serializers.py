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

    pitch = serializers.UUIDField(
        required=True,
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل معرّف UUID صحيح.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    club = serializers.UUIDField(
        required=True,
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل معرّف UUID صحيح.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    date = serializers.DateField(
        required=True,
        format='%Y-%m-%d',
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل تاريخاً صحيحاً.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )

    def validate_date(self, value):
        """
        Validate that date is not in the past
        Optional: Remove if you want to allow past dates
        """
        if value < datetime.now().date():
            raise serializers.ValidationError({"error": "تاريخ الحجز لا يمكن أن يكون في الماضي."})
        return value

class EquipmentAvailabilityQueryForUserSerializer(serializers.Serializer):
    date = serializers.DateField(
        required=True,
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل تاريخاً صحيحاً.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    start_time = serializers.TimeField(
        required=True,
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل وقتاً صحيحاً.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    end_time = serializers.TimeField(
        required=True,
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل وقتاً صحيحاً.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    club = serializers.UUIDField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل معرّف UUID صحيح.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )

    def validate(self, data):
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError({
                "error": "وقت النهاية يجب أن يكون بعد وقت البداية."
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
    club_id = serializers.UUIDField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل معرّف UUID صحيح.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )


class EquipmentBookingForUserSerializer(serializers.Serializer):
    id = serializers.UUIDField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل معرّف UUID صحيح.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    quantity = serializers.IntegerField(
        min_value=1,
        error_messages={
            'required':  'هذا الحقل مطلوب.',
            'invalid':   'أدخل عدداً صحيحاً.',
            'min_value': 'تأكد من أن هذه القيمة أكبر من أو تساوي {min_value}.',
            'null':      'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )

class BookingCreateForUserSerializer(serializers.ModelSerializer):
    equipments = EquipmentBookingForUserSerializer(many=True, required=False)
    club = serializers.UUIDField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل معرّف UUID صحيح.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )

    class Meta:
        model = Booking
        fields = ['club', 'pitch', 'date', 'start_time', 'end_time',  'price', 'final_price', 'equipments']
        extra_kwargs = {
            'price': {
                'read_only': True,
            },
            'final_price': {
                'read_only': True,
            },
            'pitch': {
                'error_messages': {
                    'required':       'هذا الحقل مطلوب.',
                    'does_not_exist': 'الملعب المحدد غير موجود.',
                    'incorrect_type': 'نوع البيانات غير صحيح.',
                    'null':           'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
            'date': {
                'error_messages': {
                    'required': 'هذا الحقل مطلوب.',
                    'invalid':  'أدخل تاريخاً صحيحاً.',
                    'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
            'start_time': {
                'error_messages': {
                    'required': 'هذا الحقل مطلوب.',
                    'invalid':  'أدخل وقتاً صحيحاً.',
                    'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
            'end_time': {
                'error_messages': {
                    'required': 'هذا الحقل مطلوب.',
                    'invalid':  'أدخل وقتاً صحيحاً.',
                    'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
        }

    def validate_date(self, value):
        today = date.today()
        if not (today + timedelta(days=settings.MIN_NUM_DAY_BEFORE_BOOKING) <= value <= today + timedelta(days=settings.MAX_NUM_DAY_BEFORE_BOOKING)):
            raise serializers.ValidationError({"error": f'تاريخ الحجز يجب أن يكون بين {settings.MIN_NUM_DAY_BEFORE_BOOKING} و {settings.MAX_NUM_DAY_BEFORE_BOOKING} يومًا من اليوم.'})
        return value

    def validate(self, attrs):
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError({"error": "وقت النهاية يجب أن يكون بعد وقت البداية."})

        day_number = (attrs['date'].weekday() + 2) % 7
        print(f"Day Number: {day_number}")
        print(attrs["club"])
        print(type(attrs["club"]))
        is_date_off = ClubPricing.objects.filter(club_id=attrs["club"], type=2, date=attrs["date"]).exists()
        is_day_off = Club.objects.values('working_days').filter(id=attrs["club"], is_active=True).first()
        if not is_day_off:
            raise serializers.ValidationError({"error": "النادي غير نشط."})

        print(is_day_off)
        if not (is_day_off['working_days'][str(day_number)] or is_date_off):
            raise serializers.ValidationError({"error": "لا يمكن الحجز في هذا اليوم لأن النادي مغلق."})
        print("//////////////////////////")
        pitch_exist = attrs['pitch'].club_id!=attrs['club'] or attrs['pitch'].is_deteted==True or attrs['pitch'].is_active==False
        print(pitch_exist)
        if pitch_exist:
            raise serializers.ValidationError({"error": "هذا الملعب لا ينتمي لهذا النادي."})
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
            raise serializers.ValidationError({"error": "هذا الوقت يتداخل مع حجز موجود."})

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
            raise serializers.ValidationError({"error": "هذا الوقت يتداخل مع حجز موجود."})

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
    id = serializers.UUIDField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل معرّف UUID صحيح.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    quantity = serializers.IntegerField(
        min_value=1,
        error_messages={
            'required':  'هذا الحقل مطلوب.',
            'invalid':   'أدخل عدداً صحيحاً.',
            'min_value': 'تأكد من أن هذه القيمة أكبر من أو تساوي {min_value}.',
            'null':      'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )

class BookingPriceRequestForUserSerializer(serializers.ModelSerializer):
    equipments = EquipmentBookingSerializer(many=True, required=False)

    class Meta:
        model = Booking
        fields = ['pitch', 'date', 'start_time', 'end_time', 'equipments', 'club']
        extra_kwargs = {
            'pitch': {
                'error_messages': {
                    'required':       'هذا الحقل مطلوب.',
                    'does_not_exist': 'الملعب المحدد غير موجود.',
                    'incorrect_type': 'نوع البيانات غير صحيح.',
                    'null':           'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
            'date': {
                'error_messages': {
                    'required': 'هذا الحقل مطلوب.',
                    'invalid':  'أدخل تاريخاً صحيحاً.',
                    'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
            'start_time': {
                'error_messages': {
                    'required': 'هذا الحقل مطلوب.',
                    'invalid':  'أدخل وقتاً صحيحاً.',
                    'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
            'end_time': {
                'error_messages': {
                    'required': 'هذا الحقل مطلوب.',
                    'invalid':  'أدخل وقتاً صحيحاً.',
                    'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
            'club': {
                'error_messages': {
                    'required': 'هذا الحقل مطلوب.',
                    'invalid':  'أدخل معرّف UUID صحيح.',
                    'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
        }

    def validate(self, attrs):
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError({"error": "وقت النهاية يجب أن يكون بعد وقت البداية."})
        return attrs