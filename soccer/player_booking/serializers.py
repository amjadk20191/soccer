from rest_framework import serializers

from dashboard_manage.models import Club, ClubPricing, Pitch
from management.models import Feature
from soccer.enm import BOOKING_STATUS_DENIED
from  player_booking.models import Booking, BookingStatus, Coupon, PayStatus, BookingEquipment
from django.db import transaction
from django.conf import settings
from datetime import date, timedelta
from core.services.CouponService import CouponService
from dashboard_booking.services.PricingService import PricingService
from dashboard_booking.services.EquipmentBookingService import EquipmentBookingService
from datetime import datetime
from player_competition.models import Challenge
from itertools import groupby

from .services.BookingHistoryService import UserBookingItem



class PitchInBookingSerializer(serializers.Serializer):
    id   = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)


class ClubInBookingSerializer(serializers.Serializer):
    id   = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)


class PlayerInChallengeSerializer(serializers.Serializer):
    id            = serializers.UUIDField(source='player.id',             read_only=True)
    full_name     = serializers.CharField(source='player.full_name',      read_only=True)
    username      = serializers.CharField(source='player.username',       read_only=True)
    image         = serializers.SerializerMethodField()

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.player.image:
            return request.build_absolute_uri(obj.player.image.url) if request else obj.player.image.url
        return None


class TeamInChallengeSerializer(serializers.Serializer):
    id      = serializers.UUIDField(read_only=True)
    name    = serializers.CharField(read_only=True)
    logo    = serializers.SerializerMethodField()
    # players = serializers.SerializerMethodField()

    def get_logo(self, obj):
        request = self.context.get('request')
        if obj.logo and obj.logo.logo:
            return request.build_absolute_uri(obj.logo.logo.url) if request else obj.logo.logo.url
        return None

    # def get_players(self, obj):
    #     # challenge_players is injected via context — already grouped by team
    #     team_players = self.context.get('team_players', {})
    #     players = team_players.get(str(obj.id), [])
    #     return PlayerInChallengeSerializer(players, many=True, context=self.context).data


class ChallengeDetailSerializer(serializers.ModelSerializer):
    status          = serializers.CharField(source='get_status_display', read_only=True)
    team            = serializers.SerializerMethodField()
    challenged_team = serializers.SerializerMethodField()

    class Meta:
        model  = Challenge
        fields = [
            'id',
            'status',
            'team',
            'result_team',
            'challenged_team',
            'result_challenged_team',

        ]

    def get_team(self, obj):
        return TeamInChallengeSerializer(obj.team, context=self.context).data

    def get_challenged_team(self, obj):
        return TeamInChallengeSerializer(obj.challenged_team, context=self.context).data

class BookingEquipmentSerializer(serializers.Serializer):
    name = serializers.CharField(source="equipment_def.name")
    description = serializers.CharField(source="equipment_def.description")
    image = serializers.SerializerMethodField()
    quantity = serializers.IntegerField()

    def get_image(self, obj):
        request = self.context.get("request")
        image_field = obj.equipment_def.image

        if not image_field:
            return None

        return request.build_absolute_uri(image_field.url) if request else image_field.url


class BookingDetailSerializer(serializers.ModelSerializer):
    status_display         = serializers.CharField(source='get_status_display',         read_only=True)
    payment_status = serializers.CharField(source='get_payment_status_display', read_only=True)
    pitch          = PitchInBookingSerializer(read_only=True)
    club           = ClubInBookingSerializer(read_only=True)
    challenge      = serializers.SerializerMethodField()
    equipment = BookingEquipmentSerializer(
        source='bookingequipment_set',
        many=True,
        read_only=True
    )
    is_coupon = serializers.SerializerMethodField()
    
    class Meta:
        model  = Booking
        fields = [
            'id',
            'date',
            'start_time',
            'end_time',
            'price',
            'final_price',
            'deposit',
            'status',
            'status_display',
            'payment_status',
            'is_challenge',
            'pitch',
            'club',
            'challenge',
            'equipment',
            'is_coupon',
            'created_at'
        ]

    def get_challenge(self, obj):
        challenges = getattr(obj, 'challenges', [])
        if not challenges:
            return None

        # Group prefetched players by team_id — no DB hit
        team_players = {}
        for cp in getattr(obj, 'challenge_players', []):
            team_players.setdefault(str(cp.team_id), []).append(cp)

        context = {**self.context, 'team_players': team_players}
        return ChallengeDetailSerializer(challenges[0], context=context).data

    def get_is_coupon(self, obj):
        return obj.coupon_id is not None



class ChallengeResultSerializer(serializers.ModelSerializer):
    team             = TeamInChallengeSerializer(read_only=True)
    challenged_team  = TeamInChallengeSerializer(read_only=True)


    class Meta:
        model  = Challenge
        fields = [
            'id',
            'team',             # full object with id, name, logo
            'result_team',
            'challenged_team',  # full object with id, name, logo
            'result_challenged_team',

        ]


class UserBookingSerializer(serializers.Serializer):
    # entry_type     = serializers.CharField()
    id             = serializers.UUIDField()
    date           = serializers.DateField()
    start_time     = serializers.TimeField()
    end_time       = serializers.TimeField()
    final_price    = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    status         = serializers.IntegerField(allow_null=True)
    status_display = serializers.SerializerMethodField()
    # pitch_id       = serializers.UUIDField(allow_null=True)
    pitch_name     = serializers.CharField(allow_null=True)
    # club_id        = serializers.UUIDField(allow_null=True)
    club_name      = serializers.CharField(allow_null=True)
    challenge      = serializers.SerializerMethodField()
    is_booking     = serializers.SerializerMethodField() 
    def get_status_display(self, obj: UserBookingItem):
        return obj.get_status_display()

    def get_challenge(self, obj: UserBookingItem):
        if obj.challenge_id is None:
            return None
        request = self.context.get('request')

        def logo_url(path):
            if not path:
                return None
            return request.build_absolute_uri(f'/media/{path}') if request else f'/media/{path}'

        return {
            'id':                     obj.challenge_id,
            'status':                 obj.challenge_status,
            'result_team':            obj.result_team,
            'result_challenged_team': obj.result_challenged_team,
            'team': {
                'id':   obj.team_id,
                'name': obj.team_name,
                'logo': logo_url(obj.team_logo),
            },
            'challenged_team': {
                'id':   obj.challenged_team_id,
                'name': obj.challenged_team_name,
                'logo': logo_url(obj.challenged_team_logo),
            },
        }    
    def get_is_booking(self, obj: UserBookingItem) -> bool:
        return obj.entry_type == 'booking'

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

class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ['id', 'code', 'discount_type', 'discount_value', 'is_active', 'expires_at', 'max_uses', 'used_count', 'club']
        extra_kwargs = {
            'club': {'read_only': True},  # ✅ set automatically, not from request body
            'used_count': {'read_only': True},
        }

class BookingCreateForUserSerializer(serializers.ModelSerializer):
    equipments = EquipmentBookingForUserSerializer(many=True, required=False)
    coupon_code = serializers.CharField(required=False, allow_null=True, allow_blank=True, )
    club = serializers.UUIDField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل معرّف UUID صحيح.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )

    class Meta:
        model = Booking
        fields = ['club', 'pitch', 'date', 'start_time', 'end_time', 'price', 'final_price', 'equipments', 'coupon_code']
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
            status__in= [                   # BOOKING_STATUS_DENIED
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
            raise serializers.ValidationError({"error": "هذا الوقت يتداخل مع حجز موجود لديك."})

        return attrs

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['coupon_code'] = getattr(instance, '_applied_coupon_code', None)
        return ret
    
    def create(self, validated_data):
        club_id = validated_data.pop('club')
        user_id = self.context['request'].auth.get('user_id')
        request_user = self.context['request'].user
        coupon_code = validated_data.pop('coupon_code', None) or None
        price = PricingService.calculate_final_price(validated_data['pitch'], club_id, validated_data['date'], validated_data['start_time'], validated_data['end_time'])
        equipments = validated_data.pop("equipments", [])

        with transaction.atomic():
            booking = Booking.objects.create(
                club_id=club_id,
                player_id=user_id,
                price=price,
                final_price=price,
                **validated_data)
            current_final_price = booking.final_price
            if equipments:
                final_price_with_equipments_ = EquipmentBookingService.Create_Equipment_Booking(club_id, booking, equipments, validated_data['start_time'],  validated_data['end_time'])
            applied_coupon = None
            if coupon_code:
                coupon_result = CouponService.apply_coupon(
                    current_final_price,
                    coupon_code,
                    user=request_user,
                    club_id=club_id
                )
                current_final_price = coupon_result['price']
                applied_coupon = coupon_result['coupon']
  
            booking.final_price=final_price_with_equipments_
            booking._force_signals_update = booking.status==BookingStatus.COMPLETED
            booking.save(update_fields=['final_price', 'updated_at'])

            if applied_coupon:
                CouponService.redeem_coupon(applied_coupon, user=request_user)
        booking._applied_coupon_code = coupon_code
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

class PitchSearchSerializer(serializers.Serializer):
    date = serializers.DateField(required=True)
    start_time = serializers.TimeField(required=True)
    end_time = serializers.TimeField(required=True)
    user_latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    user_longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    type = serializers.CharField(required=False, allow_null=True)
    size_high = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    size_width = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)

    def validate(self, attrs):
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError({"error": "وقت النهاية يجب أن يكون بعد وقت البداية."})
        return attrs

class PitchSearchResultSerializer(serializers.ModelSerializer):
    club_name         = serializers.CharField(source='club.name')
    club_address      = serializers.CharField(source='club.address')
    club_latitude     = serializers.DecimalField(source='club.latitude', max_digits=9, decimal_places=6)
    club_longitude    = serializers.DecimalField(source='club.longitude', max_digits=9, decimal_places=6)
    club_logo         = serializers.ImageField(source='club.logo')
    club_rating_avg   = serializers.DecimalField(source='club.rating_avg', max_digits=3, decimal_places=2)
    club_rating_count = serializers.IntegerField(source='club.rating_count')

    club_open_time  = serializers.SerializerMethodField()
    club_close_time = serializers.SerializerMethodField()
    # distance_km     = serializers.SerializerMethodField()

    class Meta:
        model = Pitch
        fields = [
            'id', 'name', 'type', 'image',
            'size_high', 'size_width',
            # 'price_first', 'price_second',
            # 'time_interval',
            'club_name', 'club_address',
            'club_latitude', 'club_longitude',
            'club_logo',
            'club_open_time', 'club_close_time',
            'club_rating_avg', 'club_rating_count',
            # 'distance_km',
        ]

    def get_club_open_time(self, obj):
        # effective_open attached by the view after pagination
        return getattr(obj, 'effective_open', obj.club.open_time)

    def get_club_close_time(self, obj):
        return getattr(obj, 'effective_close', obj.club.close_time)

    # def get_distance_km(self, obj):
    #     return round(getattr(obj, 'distance_km', 0), 2)    


class BookingPriceRequestForUserSerializer(serializers.ModelSerializer):
    equipments = EquipmentBookingSerializer(many=True, required=False)

    class Meta:
        model = Booking
        fields = ['pitch', 'date', 'start_time', 'end_time', 'equipments', 'club', 'coupon_code']
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