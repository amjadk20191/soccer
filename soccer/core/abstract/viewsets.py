# core/viewsets.py
from django.db import transaction
from rest_framework.viewsets import ModelViewSet

class TransactionalModelViewSet(ModelViewSet):
    """
    Base ViewSet that wraps create/update/delete
    operations in a database transaction.
    """

    def perform_create(self, serializer):
        with transaction.atomic():
            return super().perform_create(serializer)

    def perform_update(self, serializer):
        with transaction.atomic():
            return super().perform_update(serializer)

    def perform_destroy(self, instance):
        with transaction.atomic():
            return super().perform_destroy(instance)
