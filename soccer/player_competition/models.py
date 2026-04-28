from django.db import models
from django.utils.translation import gettext_lazy as _
from player_team.models import Team
from dashboard_manage.models import ClubEquipment, Pitch, Club
from core.models import User
from player_booking.models import Booking
import uuid
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


class ChallengeStatus(models.IntegerChoices):
    PENDING_TEAM = 1, _('بانتظار الفريق')   # waiting for challenged team to accept/reject
    PENDING_OWNER = 2, _('بانتظار المالك')
    PENDING_PAY = 3, _('بانتظار الدفع')
    ACCEPTED = 4, _('مقبول')
    REJECTED = 5, _('مرفوض')
    CANCELED = 6, _('ملغى')
    NO_SHOW = 7, _('لم يحضر')
    DISPUTED_SCORE = 8, _('مشكلة في النتيجة')
    DISPUTED = 9, _('مشكلة')
    EXPIRED = 10, _('انتهت صلاحيته')


class Challenge(models.Model):
    """Challenge between teams"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, blank=True, null=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='sended_challenge')
    challenged_team = models.ForeignKey(Team, on_delete=models.CASCADE)
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    # created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    result_team = models.PositiveSmallIntegerField(default=0)
    result_challenged_team = models.PositiveSmallIntegerField(default=0)
    status = models.PositiveSmallIntegerField(choices=ChallengeStatus.choices, default=ChallengeStatus.PENDING_TEAM)
    note_admin = models.TextField(blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'challenges'
        verbose_name = _('Challenge')
        verbose_name_plural = _('Challenges')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['booking']),
            models.Index(fields=['date']),
            models.Index(fields=['team']),
            models.Index(fields=['challenged_team']),
            models.Index(fields=['status', 'created_at']),

        ]
    

# this table for save players who played the game (booking/challenge)
#this instert happen after convert booking status to PENDING_PAY
class ChallengePlayerBooking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE)
    player = models.ForeignKey(User, on_delete=models.CASCADE)


    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['challenge', 'player'],
                name='unique_player_per_challenge'
            )
        ]
        indexes = [
        models.Index(fields=['booking_id', 'player_id']),
        ]


class ChallengeEquipment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE)
    equipment = models.ForeignKey(ClubEquipment, on_delete=models.CASCADE)
    # equipment_def = models.ForeignKey(Equipment, on_delete=models.CASCADE)
    # name = models.CharField(max_length=100)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    # price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)