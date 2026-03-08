from django.db import models
from django.utils.translation import gettext_lazy as _
from player_team.models import Team
from dashboard_manage.models import Pitch, Club
from core.models import User
from player_booking.models import Booking
import uuid


class ChallengeStatus(models.IntegerChoices):
    PENDING_TEAM = 1, _('Pending-Team')
    PENDING_OWNER = 2, _('Pending-Owner')
    PENDING_PAY = 3, _('Pending-Pay')
    ACCEPTED = 4, _('Accepted')
    REJECTED = 5, _('Rejected')
    CANCELED = 6, _('Canceled')


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
        ]
    

