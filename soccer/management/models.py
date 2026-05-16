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



class RequestErrorLog(models.Model):
    """Immutable log of unhandled 500 errors — written by ErrorLoggingMiddleware."""

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4)

    # ── Request ───────────────────────────────────────────────────────────
    method          = models.CharField(max_length=10)
    path            = models.TextField()
    query_params    = models.TextField(blank=True)
    request_body    = models.TextField(blank=True)
    request_headers = models.JSONField(default=dict)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)
    user_agent      = models.TextField(blank=True)

    # ── Auth ──────────────────────────────────────────────────────────────
    user_id         = models.CharField(max_length=255, blank=True)   # str to support UUID / int

    # ── Exception ─────────────────────────────────────────────────────────
    exception_type  = models.CharField(max_length=255)
    exception_msg   = models.TextField()
    traceback       = models.TextField()

    # ── Response ──────────────────────────────────────────────────────────
    status_code     = models.PositiveSmallIntegerField(default=500)

    # ── Meta ──────────────────────────────────────────────────────────────
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering   = ['-created_at']


    def __str__(self):
        return f"[{self.status_code}] {self.method} {self.path} — {self.exception_type}"
    





    """
Drop this model into your Django app (e.g.  transactions/models.py).

The scraper feeds this table directly via raw SQL — no Django process needed
at scrape time.  Django manages migrations and the DRF serializer/viewset as
normal.

Table name the scraper expects:  <app_label>_transaction
Set DB_TABLE env var to match, e.g.:
    DB_TABLE=transactions_transaction
"""

from django.db import models


class Transaction(models.Model):
    """
    Populated by the ShamCash scraper.
    The scraper writes directly via Django ORM (bulk_create, ignore_conflicts=True).
    Table name: management_transaction
    """
 
    class Direction(models.TextChoices):
        IN  = "+", "Incoming"
        OUT = "-", "Outgoing"
 
    # ── core fields ───────────────────────────────────────────────────────────
    tx_id     = models.CharField(max_length=50, primary_key=True, verbose_name="Transaction ID")
    name      = models.CharField(max_length=255, verbose_name="Counterparty name")
    date      = models.DateField()
    time      = models.TimeField()
    amount    = models.DecimalField(max_digits=15, decimal_places=2)
    currency  = models.CharField(max_length=10, default="SYP")
    direction = models.CharField(max_length=1, choices=Direction.choices)
    notes     = models.TextField(blank=True, default="")
 
    # ── metadata ──────────────────────────────────────────────────────────────
    scraped_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        ordering = ["-date", "-time"]
        indexes  = [
            models.Index(fields=["date"]),
            models.Index(fields=["direction"]),
        ]
 
    def __str__(self) -> str:
        sign = "+" if self.direction == self.Direction.IN else "-"
        return f"{self.name}  {sign}{self.amount} {self.currency}  ({self.date})"