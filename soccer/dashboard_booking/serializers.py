from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import  BookingNotification
from  player_booking.models import Booking, BookingStatus, PayStatus, BookingEquipment
from dashboard_manage.models import Pitch
from dashboard_booking.services.PricingService import PricingService
from .services.EquipmentBookingService import EquipmentBookingService
from soccer.enm import BOOKING_STATUS_DENIED
from django.db import transaction


User = get_user_model()




class ClosedBookingCreateSerializer(serializers.ModelSerializer):


    class Meta:
        model = Booking
        fields = ['pitch', 'date', 'start_time', 'end_time', 'note_owner']
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
            'note_owner': {
                'error_messages': {
                    'blank':      'لا يمكن أن يكون هذا الحقل فارغاً.',
                    'max_length': 'تأكد من أن هذه القيمة لا تحتوي على أكثر من {max_length} حرف.',
                }
            },
        }


    def validate_pitch(self, value):
        club_id = self.context['request'].auth.get('club_id')

        if str(value.club_id) != club_id and not value.is_active and value.is_deteted:
            raise serializers.ValidationError({"error": "الملعب  لا ينتمي إلى النادي."})
        return value

    def validate(self, attrs):
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError({"error": "وقت النهاية يجب أن يكون بعد وقت البداية."})

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

        return attrs

    def create(self, validated_data):
        club_id = self.context['request'].auth.get('club_id')

        with transaction.atomic():
            booking = Booking.objects.create(
                club_id=club_id,
                price=0,
                by_owner=True,
                final_price=0,
                status=BookingStatus.CLOSED.value,
                **validated_data)

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


class EquipmentAvailabilityQuerySerializer(serializers.Serializer):
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

    def validate(self, data):
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError({
                "error": "وقت البداية يجب أن يكون قبل وقت النهاية."
            })
        return data

class BookingListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'start_time', 'end_time', 'price', 'status_display', 'player_name'
        ]


class BookingEquipmentDetailSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='equipment_def.name', read_only=True)
    image = serializers.ImageField(source='equipment_def.image', read_only=True)

    class Meta:
        model = BookingEquipment
        fields = ['id', 'name', 'image', 'quantity', 'price']


class BookingDetailSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source='player.username', read_only=True, allow_null=True)
    full_name = serializers.CharField(source='player.username', read_only=True, allow_null=True)
    pitch_name = serializers.CharField(source='pitch.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status = serializers.CharField(source='get_payment_status_display', read_only=True)
    equipments = BookingEquipmentDetailSerializer(source='bookingequipment_set', many=True, read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'date', 'start_time', 'end_time', 'price', 'final_price', 'status_display',
            'created_at', 'updated_at', 'player_name', 'full_name', 'pitch_name', 'phone', 'by_owner',
            'payment_status','note_owner', 'equipments'
        ]

class BookingListPitchSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source='player.username', read_only=True, allow_null=True)
    full_name = serializers.CharField(source='player.username', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    price= serializers.FloatField(source='final_price')

    class Meta:
        model = Booking
        fields = [
            'id', 'date', 'start_time', 'end_time', 'price', 'deposit', 'status_display', 'is_challenge',
            'player_name', 'full_name', 'phone', 'by_owner'
        ]

class BookingCreateSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        write_only=True,
        required=False,
        allow_null=True,
        allow_blank=True,
        error_messages={
            'blank':      'لا يمكن أن يكون هذا الحقل فارغاً.',
            'max_length': 'تأكد من أن هذه القيمة لا تحتوي على أكثر من {max_length} حرف.',
        }
    )
    equipments = EquipmentBookingSerializer(many=True, required=False)

    class Meta:
        model = Booking
        fields = ['pitch', 'date', 'start_time', 'end_time', 'username', 'phone', 'note_owner', 'payment_status', 'status', 'deposit', 'price', 'final_price', 'equipments']
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
            'phone': {
                'error_messages': {
                    'blank':    'لا يمكن أن يكون هذا الحقل فارغاً.',
                    'invalid':  'أدخل رقم هاتف صحيح.',
                    'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
            'note_owner': {
                'error_messages': {
                    'blank':      'لا يمكن أن يكون هذا الحقل فارغاً.',
                    'max_length': 'تأكد من أن هذه القيمة لا تحتوي على أكثر من {max_length} حرف.',
                }
            },
            'payment_status': {
                'error_messages': {
                    'required':       'هذا الحقل مطلوب.',
                    'invalid_choice': 'القيمة "{input}" غير صحيحة.',
                }
            },
            'status': {
                'error_messages': {
                    'required':       'هذا الحقل مطلوب.',
                    'invalid_choice': 'القيمة "{input}" غير صحيحة.',
                }
            },
            'deposit': {
                'error_messages': {
                    'invalid':   'أدخل رقماً صحيحاً.',
                    'max_value': 'تأكد من أن هذه القيمة أقل من أو تساوي {max_value}.',
                    'min_value': 'تأكد من أن هذه القيمة أكبر من أو تساوي {min_value}.',
                }
            },
        }

    def is_valid_username(self, value):

        if value:
            try:
                user = User.objects.get(username=value, role=1)
                return user
            except User.DoesNotExist:

                raise serializers.ValidationError({"username": f"اسم المستخدم {value} غير موجود."})

    def validate_pitch(self, value):
        club_id = self.context['request'].auth.get('club_id')

        if str(value.club_id) != club_id and not value.is_active and value.is_deteted:
            raise serializers.ValidationError({"error": "الملعب  لا ينتمي إلى النادي."})
        return value

    def validate(self, attrs):
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError({"error": "وقت النهاية يجب أن يكون بعد وقت البداية."})

        payment_status = attrs.get('payment_status', PayStatus.UNKNOWN.value)
        status = attrs.get('status')

        if not(status == BookingStatus.COMPLETED.value or status == BookingStatus.PENDING_PAY.value) :
            raise serializers.ValidationError({"status":"الحالة يجب أن تكون مكتملة أو في انتظار الدفع."})

        # payment_status "PENDING_PAY" shoulb be DEPOSIT or LATER
        if status == BookingStatus.PENDING_PAY.value and not(payment_status == PayStatus.LATER.value or payment_status == PayStatus.DEPOSIT.value):
            raise serializers.ValidationError({"error":"حالة الدفع يجب أن تكون لاحقًا أو دفعة مقدمة إذا كانت حالة الحجز في انتظار الدفع."})

        # if the payment_status is "Deposit" then deposit field should be grater than 0
        if payment_status == PayStatus.DEPOSIT.value and attrs.get('deposit', 0) < 0:
            raise serializers.ValidationError({"error": "الدفعة المقدمة يجب أن تكون أكبر من صفر."})

        # there should only one of (phone, username)
        has_phone = "phone" in attrs
        has_username = "username" in attrs
        if has_phone == has_username:
            raise serializers.ValidationError({"error": "رجاء تقديم إما رقم هاتف أو اسم مستخدم، وليس كلاهما."})

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

        return attrs

    def create(self, validated_data):
        username = validated_data.pop('username', None)
        user = self.is_valid_username(username) if username else None
        club_id = self.context['request'].auth.get('club_id')
        price = PricingService.calculate_final_price(validated_data['pitch'], club_id, validated_data['date'], validated_data['start_time'], validated_data['end_time'])

        if validated_data['status'] == BookingStatus.COMPLETED.value:
            validated_data['payment_status'] = PayStatus.UNKNOWN.value

        # delete deposit if payment_status what not deposit
        if validated_data.get('payment_status', PayStatus.DEPOSIT.value) != PayStatus.DEPOSIT.value:
            validated_data.pop('deposit', None)
        equipments = validated_data.pop("equipments",[])

        with transaction.atomic():
            booking = Booking.objects.create(
                club_id=club_id,
                player=user,
                price=price,
                by_owner=True,
                final_price=price,
                **validated_data)
            if equipments:
                final_price_with_equipments_ = EquipmentBookingService.Create_Equipment_Booking(club_id, booking, equipments, validated_data['start_time'],  validated_data['end_time'])
                
                
                booking.final_price=final_price_with_equipments_
                booking._force_signals_update = booking.status==BookingStatus.COMPLETED
                booking.save(update_fields=['final_price', 'updated_at'])
        return booking

class BookingUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ['date', 'start_time', 'end_time', 'price']
        extra_kwargs = {
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
            'price': {
                'error_messages': {
                    'required':  'هذا الحقل مطلوب.',
                    'invalid':   'أدخل رقماً صحيحاً.',
                    'max_value': 'تأكد من أن هذه القيمة أقل من أو تساوي {max_value}.',
                    'min_value': 'تأكد من أن هذه القيمة أكبر من أو تساوي {min_value}.',
                }
            },
        }

    def validate(self, attrs):
        start_time = attrs.get('start_time', self.instance.start_time)
        end_time = attrs.get('end_time', self.instance.end_time)

        if start_time >= end_time:
            raise serializers.ValidationError({"error": "وقت النهاية يجب أن يكون بعد وقت البداية."})

        return attrs

class BookingRescheduleSerializer(serializers.Serializer):
    """Serializer for rescheduling booking (Pending_manager -> Pending_player)"""
    new_date = serializers.DateField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل تاريخاً صحيحاً.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    new_start_time = serializers.TimeField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل وقتاً صحيحاً.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    new_end_time = serializers.TimeField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل وقتاً صحيحاً.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )

    def validate(self, attrs):
        if attrs['new_start_time'] >= attrs['new_end_time']:
            raise serializers.ValidationError({"error": "وقت النهاية يجب أن يكون بعد وقت البداية."})
        return attrs

class BookingSlotFilterSerializer(serializers.Serializer):
    date = serializers.DateField(
        format='%Y-%m-%d',
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل تاريخاً صحيحاً.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    pitch_id = serializers.UUIDField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل معرّف UUID صحيح.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    time_from = serializers.TimeField(
        format='%H:%M',
        required=False,
        error_messages={
            'invalid': 'أدخل وقتاً صحيحاً.',
        }
    )
    time_to = serializers.TimeField(
        format='%H:%M',
        required=False,
        error_messages={
            'invalid': 'أدخل وقتاً صحيحاً.',
        }
    )

    def validate(self, data):

        if data.get('from_time') and data.get('to_time'):
            if data['from_time'] >= data['to_time']:
                raise serializers.ValidationError({"error": "وقت البداية يجب أن يكون قبل وقت النهاية."})
        return data


class BookingPriceRequestSerializer(serializers.ModelSerializer):
    equipments = EquipmentBookingSerializer(many=True, required=False)

    class Meta:
        model = Booking
        fields = ['pitch', 'date', 'start_time', 'end_time', 'equipments']
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
        }

    def validate(self, attrs):
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError({"error": "وقت النهاية يجب أن يكون بعد وقت البداية."})
        return attrs

class BookingConvertStatusSerializer(serializers.ModelSerializer):

    class Meta:
        model = Booking
        fields = ['status']
        extra_kwargs = {
            'status': {
                'error_messages': {
                    'required':       'هذا الحقل مطلوب.',
                    'invalid_choice': 'القيمة "{input}" غير صحيحة.',
                    'null':           'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
        }