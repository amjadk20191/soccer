import re

from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User

from .validators import validate_phone_format


class CheckAvailabilityInputSerializer(serializers.Serializer):
    username = serializers.CharField(
        max_length=150,
        trim_whitespace=True,
        error_messages={
            'required': 'اسم المستخدم مطلوب.',
            'blank': 'اسم المستخدم لا يمكن أن يكون فارغاً.',
            'max_length': 'اسم المستخدم يجب أن لا يتجاوز 150 حرفاً.',
        }
    )
    phone = serializers.CharField(
        max_length=10,
        trim_whitespace=True,
        error_messages={
            'required': 'رقم الهاتف مطلوب.',
            'blank': 'رقم الهاتف لا يمكن أن يكون فارغاً.',
            'max_length': 'رقم الهاتف يجب أن لا يتجاوز 10 أرقام.',
        }
    )

    def validate_phone(self, value):
        validate_phone_format(value)
        return value


    
class UserRegistrationSerializer(serializers.ModelSerializer):

    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'blank':    'لا يمكن أن يكون هذا الحقل فارغاً.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )

    class Meta:
        model = User
        fields = [
            'phone', 'password', 'full_name', 'username',
            'birthday', 'height', 'weight', 'foot_preference'
        ]
        extra_kwargs = {
            'phone': {
                'error_messages': {
                    'required': 'هذا الحقل مطلوب.',
                    'blank':    'لا يمكن أن يكون هذا الحقل فارغاً.',
                    'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
                    'invalid':  'أدخل رقم هاتف صحيح.',
                }
            },
            'full_name': {
                'error_messages': {
                    'required':   'هذا الحقل مطلوب.',
                    'blank':      'لا يمكن أن يكون هذا الحقل فارغاً.',
                    'null':       'لا يمكن أن تكون هذه القيمة فارغة.',
                    'max_length': 'تأكد من أن هذه القيمة لا تحتوي على أكثر من {max_length} حرف.',
                }
            },
            'username': {
                'error_messages': {
                    'required':   'هذا الحقل مطلوب.',
                    'blank':      'لا يمكن أن يكون هذا الحقل فارغاً.',
                    'null':       'لا يمكن أن تكون هذه القيمة فارغة.',
                    'max_length': 'تأكد من أن هذه القيمة لا تحتوي على أكثر من {max_length} حرف.',
                }
            },
            'birthday': {
                'error_messages': {
                    'required': 'هذا الحقل مطلوب.',
                    'invalid':  'أدخل تاريخ ميلاد صحيح.',
                    'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
            'height': {
                'error_messages': {
                    'required':  'هذا الحقل مطلوب.',
                    'invalid':   'أدخل قيمة صحيحة للطول.',
                    'max_value': 'تأكد من أن الطول أقل من أو يساوي {max_value}.',
                    'min_value': 'تأكد من أن الطول أكبر من أو يساوي {min_value}.',
                    'null':      'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
            'weight': {
                'error_messages': {
                    'required':  'هذا الحقل مطلوب.',
                    'invalid':   'أدخل قيمة صحيحة للوزن.',
                    'max_value': 'تأكد من أن الوزن أقل من أو يساوي {max_value}.',
                    'min_value': 'تأكد من أن الوزن أكبر من أو يساوي {min_value}.',
                    'null':      'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
            'foot_preference': {
                'error_messages': {
                    'required':       'هذا الحقل مطلوب.',
                    'invalid_choice': 'القيمة "{input}" غير صحيحة.',
                    'null':           'لا يمكن أن تكون هذه القيمة فارغة.',
                }
            },
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        return user


class LoginSerializer(serializers.Serializer):

    phone = serializers.CharField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'blank':    'لا يمكن أن يكون هذا الحقل فارغاً.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    password = serializers.CharField(
        write_only=True,
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'blank':    'لا يمكن أن يكون هذا الحقل فارغاً.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )

    def validate(self, attrs):
        phone = attrs.get('phone')
        password = attrs.get('password')

        if phone and password:

            user = authenticate(request=self.context.get('request'), phone=phone, password=password)

            if not user:
                raise serializers.ValidationError({"error": "رقم الهاتف أو كلمة المرور غير صحيحة."})

            if not user.is_active:
                raise serializers.ValidationError({"error": "حساب المستخدم معطل."})

            attrs['user'] = user
        else:
            raise serializers.ValidationError({"error": "يرجى تقديم رقم هاتف وكلمة مرور."})

        return attrs