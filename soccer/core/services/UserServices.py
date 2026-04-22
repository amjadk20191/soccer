import os
from ..utils import DEFAULT_USER_IMAGE
from django.conf import settings
from ..models import User, UserDevice
from django.utils import timezone
from datetime import timedelta
from rest_framework import serializers


class UserService:
    @staticmethod
    def delete_user_image(user) -> None:
        """Delete user's image file from disk and reset to default."""

        if not user.image:                        
            return

        # Don't delete the default image
        if str(user.image) == DEFAULT_USER_IMAGE:
            return

        # Delete file from disk
        image_path = os.path.join(settings.MEDIA_ROOT, str(user.image))
        if os.path.exists(image_path):
            os.remove(image_path)

        # Reset to default
        user.image = DEFAULT_USER_IMAGE
        user.save(update_fields=['image'])         

    
    @staticmethod
    def update_user(user, validated_data):
        password = validated_data.pop('password', None)
        new_image = validated_data.pop('image', None)

        if new_image:
            # Check if user updated image within the last 30 days
            if user.image_updated_at:
                interval_days = getattr(settings, 'IMAGE_UPDATE_INTERVAL_DAYS', 30)  # fallback to 30 if not set
                next_allowed = user.image_updated_at + timedelta(days=interval_days)
                if timezone.now() < next_allowed:
                    days_left = (next_allowed - timezone.now()).days + 1
                    raise serializers.ValidationError({
                        'image': f'لا يمكنك تغيير الصورة إلا بعد {days_left} يوم.'
                    })

            # Delete old image if not default
            if user.image and str(user.image) != DEFAULT_USER_IMAGE:
                old_image_path = os.path.join(settings.MEDIA_ROOT, str(user.image))
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)

            user.image = new_image
            user.image_updated_at = timezone.now()      # ✅ record the update time

        for attr, value in validated_data.items():
            setattr(user, attr, value)

        if password:
            user.set_password(password)

        user.save()
        return user





class UserDeviceService:

    @staticmethod
    def register_device(user: User, fcm_token: str) -> None:
        UserDevice.objects.get_or_create(user=user, fcm_token=fcm_token)

    @staticmethod
    def remove_device(user: User, fcm_token: str) -> None:
        UserDevice.objects.filter(user=user, fcm_token=fcm_token).delete()

