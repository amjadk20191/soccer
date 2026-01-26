from django.db import models
from django.core.validators import FileExtensionValidator

from dashboard_manage.models import Club
from core.utils import upload_to_model_name

import uuid

class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=200)
    logo = models.ImageField(upload_to=upload_to_model_name,   validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "webp"], message="Only JPG, JPEG, PNG, and WEBP images are allowed." )])




class Feature(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['club', 'is_active']),
            models.Index(fields=['tag', 'is_active']),
        ]