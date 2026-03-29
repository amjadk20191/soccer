from rest_framework import serializers
from .models import Club, ClubPricing, Pitch, Equipment, ClubEquipment, BookingDuration
from .services import EquipmentManageService


class BookingDurationSerializer(serializers.ModelSerializer):
    class Meta:
            model = BookingDuration
            fields = ['id', 'duration']
            extra_kwargs = {
                'duration': {
                    'error_messages': {
                        'required':  'هذا الحقل مطلوب.',
                        'invalid':   'أدخل قيمة صحيحة للمدة.',
                        'null':      'لا يمكن أن تكون هذه القيمة فارغة.',
                        'max_value': 'تأكد من أن هذه القيمة أقل من أو تساوي {max_value}.',
                        'min_value': 'تأكد من أن هذه القيمة أكبر من أو تساوي {min_value}.',
                    }
                },
            }

    def create(self, validated_data):
        validated_data["club_id"]=self.context['request'].auth.get('club_id')
        duration_exist=BookingDuration.objects.filter(club_id=validated_data["club_id"] ,duration=validated_data["duration"]).exists()
        if duration_exist:
            raise serializers.ValidationError({"error": "المدة المحددة موجودة بالفعل."})

        return super().create(validated_data)


class CreateClubEquipmentSerializer(serializers.ModelSerializer):
    equipment_id = serializers.UUIDField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل معرّف UUID صحيح.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )

    class Meta:
        model = ClubEquipment
        fields = ['equipment_id', 'quantity', 'price', 'is_active']
        extra_kwargs = {
            'is_active': {
                'required': False,
                'error_messages': {
                    'invalid': 'أدخل قيمة صحيحة (صح/خطأ).',
                }
            },
            'quantity': {
                'error_messages': {
                    'required':  'هذا الحقل مطلوب.',
                    'invalid':   'أدخل عدداً صحيحاً.',
                    'null':      'لا يمكن أن تكون هذه القيمة فارغة.',
                    'max_value': 'تأكد من أن هذه القيمة أقل من أو تساوي {max_value}.',
                    'min_value': 'تأكد من أن هذه القيمة أكبر من أو تساوي {min_value}.',
                }
            },
            'price': {
                'error_messages': {
                    'required':  'هذا الحقل مطلوب.',
                    'invalid':   'أدخل رقماً صحيحاً.',
                    'null':      'لا يمكن أن تكون هذه القيمة فارغة.',
                    'max_value': 'تأكد من أن هذه القيمة أقل من أو تساوي {max_value}.',
                    'min_value': 'تأكد من أن هذه القيمة أكبر من أو تساوي {min_value}.',
                }
            },
        }

    def create(self, validated_data):

        club_id = self.context['request'].auth.get('club_id')
        equipment = EquipmentManageService.create_equipment(validated_data['equipment_id'], club_id, validated_data['quantity'], validated_data['price'])
        return equipment


class ShowClubEquipmentSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    name = serializers.CharField(source='equipment.name', read_only=True)
    description = serializers.CharField(source='equipment.description', read_only=True)

    class Meta:
        model = ClubEquipment
        fields = ['id', 'name', 'description','price' , 'quantity', 'image', 'is_active']

    def get_image(self, obj):

        if obj.equipment.image:
            image = obj.equipment.image
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(image.url)
            return image.url
        return None


class ReadEquipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Equipment
        fields = ['id', 'name', 'description', 'image']


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
        extra_kwargs = {
            'description': {
                'error_messages': {
                    'blank':      'لا يمكن أن يكون هذا الحقل فارغاً.',
                    'max_length': 'تأكد من أن هذه القيمة لا تحتوي على أكثر من {max_length} حرف.',
                }
            },
            'address': {
                'error_messages': {
                    'blank':      'لا يمكن أن يكون هذا الحقل فارغاً.',
                    'max_length': 'تأكد من أن هذه القيمة لا تحتوي على أكثر من {max_length} حرف.',
                }
            },
            'open_time': {
                'error_messages': {
                    'required': 'هذا الحقل مطلوب.',
                    'invalid':  'أدخل وقتاً صحيحاً.',
                    'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
            'close_time': {
                'error_messages': {
                    'required': 'هذا الحقل مطلوب.',
                    'invalid':  'أدخل وقتاً صحيحاً.',
                    'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
            'flexible_reservation': {
                'error_messages': {
                    'invalid': 'أدخل قيمة صحيحة (صح/خطأ).',
                }
            },
            'is_active': {
                'error_messages': {
                    'invalid': 'أدخل قيمة صحيحة (صح/خطأ).',
                }
            },
        }

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
                    'error': 'وقت الإغلاق يجب أن يكون بعد وقت الفتح.'
                })

        return attrs

#for 'day_of_week'
class WeekdayPricingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClubPricing
        fields = ['id', 'day_of_week', 'start_time', 'end_time', 'percent']
        read_only_fields = ['id']
        extra_kwargs = {
            'day_of_week': {
                'error_messages': {
                    'required':       'هذا الحقل مطلوب.',
                    'invalid':        'أدخل قيمة صحيحة.',
                    'invalid_choice': 'القيمة "{input}" غير صحيحة.',
                    'null':           'لا يمكن أن تكون هذه القيمة فارغة.',
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
            'percent': {
                'error_messages': {
                    'required':  'هذا الحقل مطلوب.',
                    'invalid':   'أدخل رقماً صحيحاً.',
                    'max_value': 'تأكد من أن هذه القيمة أقل من أو تساوي {max_value}.',
                    'min_value': 'تأكد من أن هذه القيمة أكبر من أو تساوي {min_value}.',
                    'null':      'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
        }

    def validate(self, attrs):
        request = self.context.get('request')

        club_id = request.auth.payload.get('club_id')

        day_of_week= attrs.get('day_of_week',None)
        if  day_of_week is None:
            raise serializers.ValidationError({"day_of_week": "هذا الحقل مطلوب."})

        if not day_of_week in [0, 1, 2, 3, 4, 5, 6]:
            raise serializers.ValidationError({"error": "يوم الأسبوع يجب أن يكون بين 0 و 6."})

        open_time = attrs.get('start_time')
        close_time = attrs.get('end_time')
        if open_time >= close_time:
            raise serializers.ValidationError({"error": "وقت النهاية يجب أن يكون بعد وقت البداية."})

        weekday=ClubPricing.objects.filter(club_id=club_id,day_of_week=attrs.get('day_of_week')).exists()

        if weekday:
            raise serializers.ValidationError({"error": "يوجد عرض لهذا اليوم من الأسبوع."})

        is_day_off = Club.objects.values('working_days').filter(id=club_id).first()
        if not is_day_off['working_days'][str(day_of_week)]:
            raise serializers.ValidationError({"error": "لا يمكن إضافة عرض لهذا اليوم لأن النادي مغلق فيه."})

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
            'percent': {
                'error_messages': {
                    'required':  'هذا الحقل مطلوب.',
                    'invalid':   'أدخل رقماً صحيحاً.',
                    'max_value': 'تأكد من أن هذه القيمة أقل من أو تساوي {max_value}.',
                    'min_value': 'تأكد من أن هذه القيمة أكبر من أو تساوي {min_value}.',
                    'null':      'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
        }

    def validate(self, attrs):
        request = self.context.get('request')

        if request and hasattr(request, 'auth') and request.auth:
            club_id = request.auth.payload.get('club_id')

        if attrs.get('date') is None:
            raise serializers.ValidationError({"date": "هذا الحقل مطلوب."})

        open_time = attrs.get('start_time')
        close_time = attrs.get('end_time')
        if open_time >= close_time:
            raise serializers.ValidationError({"error": "وقت النهاية يجب أن يكون بعد وقت البداية."})

        date=ClubPricing.objects.filter(club_id=club_id,date=attrs.get('date')).exists()

        if date:
            raise serializers.ValidationError({"error": "يوجد عرض استثنائي لهذا التاريخ."})

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
        extra_kwargs = {
            'name': {
                'error_messages': {
                    'required':   'هذا الحقل مطلوب.',
                    'blank':      'لا يمكن أن يكون هذا الحقل فارغاً.',
                    'null':       'لا يمكن أن تكون هذه القيمة فارغة.',
                    'max_length': 'تأكد من أن هذه القيمة لا تحتوي على أكثر من {max_length} حرف.',
                }
            },
            'image': {
                'error_messages': {
                    'required':      'هذا الحقل مطلوب.',
                    'invalid_image': 'أدخل صورة صحيحة.',
                    'empty':         'لا يجوز تقديم ملف فارغ.',
                    'no_name':       'يجب أن يحتوي الملف المُقدَّم على اسم.',
                }
            },
            'type': {
                'error_messages': {
                    'required':       'هذا الحقل مطلوب.',
                    'invalid_choice': 'القيمة "{input}" غير صحيحة.',
                    'null':           'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
            'size_high': {
                'error_messages': {
                    'required':  'هذا الحقل مطلوب.',
                    'invalid':   'أدخل قيمة صحيحة.',
                    'null':      'لا يمكن أن تكون هذه القيمة فارغة.',
                    'max_value': 'تأكد من أن هذه القيمة أقل من أو تساوي {max_value}.',
                    'min_value': 'تأكد من أن هذه القيمة أكبر من أو تساوي {min_value}.',
                }
            },
            'size_width': {
                'error_messages': {
                    'required':  'هذا الحقل مطلوب.',
                    'invalid':   'أدخل قيمة صحيحة.',
                    'null':      'لا يمكن أن تكون هذه القيمة فارغة.',
                    'max_value': 'تأكد من أن هذه القيمة أقل من أو تساوي {max_value}.',
                    'min_value': 'تأكد من أن هذه القيمة أكبر من أو تساوي {min_value}.',
                }
            },
            'price_first': {
                'error_messages': {
                    'required':  'هذا الحقل مطلوب.',
                    'invalid':   'أدخل رقماً صحيحاً.',
                    'null':      'لا يمكن أن تكون هذه القيمة فارغة.',
                    'max_value': 'تأكد من أن هذه القيمة أقل من أو تساوي {max_value}.',
                    'min_value': 'تأكد من أن هذه القيمة أكبر من أو تساوي {min_value}.',
                }
            },
            'price_second': {
                'error_messages': {
                    'required':  'هذا الحقل مطلوب.',
                    'invalid':   'أدخل رقماً صحيحاً.',
                    'null':      'لا يمكن أن تكون هذه القيمة فارغة.',
                    'max_value': 'تأكد من أن هذه القيمة أقل من أو تساوي {max_value}.',
                    'min_value': 'تأكد من أن هذه القيمة أكبر من أو تساوي {min_value}.',
                }
            },
            'time_interval': {
                'error_messages': {
                    'required':  'هذا الحقل مطلوب.',
                    'invalid':   'أدخل قيمة صحيحة.',
                    'null':      'لا يمكن أن تكون هذه القيمة فارغة.',
                    'max_value': 'تأكد من أن هذه القيمة أقل من أو تساوي {max_value}.',
                    'min_value': 'تأكد من أن هذه القيمة أكبر من أو تساوي {min_value}.',
                }
            },
        }

class PitchListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pitch
        fields = [
            'id', 'name', 'image', 'is_active'
        ]
        read_only_fields = ['id', 'is_active']


class PitchActivationSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(
        required=True,
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل قيمة صحيحة (صح/خطأ).',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )