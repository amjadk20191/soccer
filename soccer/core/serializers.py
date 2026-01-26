from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User

class UserRegistrationSerializer(serializers.ModelSerializer):

    password = serializers.CharField(
        write_only=True, 
        required=True, 
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = [
            'phone', 'password', 'full_name', 'username', 
            'birthday', 'height', 'weight', 'foot_preference'
        ]

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        return user


class LoginSerializer(serializers.Serializer):


    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        phone = attrs.get('phone')
        password = attrs.get('password')

        if phone and password:
            
            user = authenticate(request=self.context.get('request'), phone=phone, password=password)
            
            if not user:
                raise serializers.ValidationError('Invalid phone number or password.')
            
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled.')
                
            attrs['user'] = user
        else:
            raise serializers.ValidationError('Must include "phone" and "password".')

        return attrs

