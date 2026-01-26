from django.db import models
from django.core.validators import MinValueValidator, FileExtensionValidator

from django.utils.translation import gettext_lazy as _
from core.models import User
from core.utils import upload_to_model_name

import uuid



class MemberStatus(models.IntegerChoices):
    ACTIVE = 1, _('Active')
    OUT = 2, _('out')
    INACTIVE = 3, _('Inactive')



class Team(models.Model):
    """Team entity representing football teams"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    address = models.CharField(max_length=255, blank=True)
    time = models.CharField(max_length=255, blank=True)
    captain = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to=upload_to_model_name, validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "webp"], message="Only JPG, JPEG, PNG, and WEBP images are allowed." )])
    total_wins = models.PositiveBigIntegerField(default=0, validators=[MinValueValidator(0)])
    total_losses = models.PositiveBigIntegerField(default=0, validators=[MinValueValidator(0)])
    total_draw = models.PositiveBigIntegerField(default=0, validators=[MinValueValidator(0)])
    total_canceled = models.PositiveBigIntegerField(default=0, validators=[MinValueValidator(0)])
    goals_scored = models.PositiveBigIntegerField(default=0, validators=[MinValueValidator(0)])
    goals_conceded = models.PositiveBigIntegerField(default=0, validators=[MinValueValidator(0)])
    clean_sheet = models.PositiveBigIntegerField(default=0, validators=[MinValueValidator(0)])
    failed_to_score = models.PositiveBigIntegerField(default=0, validators=[MinValueValidator(0)])
    challenge_mode = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
           
    
    class Meta:   
        db_table = 'teams'
        verbose_name = _('Team')
        verbose_name_plural = _('Teams')
        ordering = ['-created_at']
        indexes = [
            # models.Index(fields=['captain']),
            models.Index(fields=['captain','is_active']),
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def total_matches(self):
        return self.total_wins + self.total_losses + self.total_draw
    
    @property
    def win_rate(self):
        if self.total_matches == 0:
            return 0
        return (self.total_wins / self.total_matches) * 100


class TeamMember(models.Model):
    """Team membership linking players to teams"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.SmallIntegerField(choices=MemberStatus.choices, default=MemberStatus.ACTIVE)
    joined_at = models.DateTimeField(auto_now_add=True)
    leave_at = models.DateTimeField(null=True, blank=True)
    is_captain = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'team_members'
        verbose_name = _('Team Member')
        verbose_name_plural = _('Team Members')
        indexes = [
            models.Index(fields=['team']),
            models.Index(fields=['player']),
        ]


class RecruitmentPost(models.Model):
    """Posts for team recruitment"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    post_type = models.SmallIntegerField(choices=[(1, _('Team Seeking Player')),(2, _('Player Seeking Team'))])
    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True)
    player = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    description = models.TextField()
    is_open = models.BooleanField(default=True)
    type = models.CharField(max_length=50)# GK ....
    created_at = models.DateTimeField(auto_now_add=True)

    
    class Meta:
        db_table = 'recruitment_posts'
        verbose_name = _('Recruitment Post')
        verbose_name_plural = _('Recruitment Posts')
        indexes = [
            models.Index(fields=['is_open']),
            models.Index(fields=['is_open','team']),
            models.Index(fields=['is_open','player']),
        ]


class Request(models.Model):
    """Requests for team joining or recruitment"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    recruitment_post = models.ForeignKey(RecruitmentPost, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True)
    player = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    
    class Meta:
        db_table = 'requests'
        verbose_name = _('Request')
        verbose_name_plural = _('Requests')
        indexes = [
            models.Index(fields=['recruitment_post']),
            models.Index(fields=['team']),
            models.Index(fields=['player']),
        ]
    
    def __str__(self):
        return f"Request {self.id}"

