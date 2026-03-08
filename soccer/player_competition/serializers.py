from django.utils import timezone
from rest_framework import serializers
from player_team.models import Team
from .models import Challenge
from datetime import date, timedelta
from django.conf import settings


class CreateChallengeSerializer(serializers.Serializer):
    team_id           = serializers.UUIDField()
    challenged_team_id = serializers.UUIDField()
    pitch_id          = serializers.UUIDField()
    club_id           = serializers.UUIDField()
    start_time        = serializers.TimeField()
    end_time          = serializers.TimeField()
    date              = serializers.DateField()


    def validate_date(self, value):
        today = date.today()
        print(today)
        if not (today + timedelta(days=settings.MIN_NUM_DAY_BEFORE_CHALLENGE) <= value <= today + timedelta(days=settings.MAX_NUM_DAY_BEFORE_CHALLENGE)):
            raise serializers.ValidationError(f'Date must be between {settings.MIN_NUM_DAY_BEFORE_BOOKING} and {settings.MAX_NUM_DAY_BEFORE_BOOKING} days from today.')
        return value

    def validate(self, attrs):
        if attrs['team_id'] == attrs['challenged_team_id']:
            raise serializers.ValidationError("A team cannot challenge itself.")
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError("start_time must be before end_time.")
        return attrs


class ShowChallengeTeamsSerializer(serializers.ModelSerializer):
    avg_player_age  = serializers.FloatField(read_only=True)
    active_member_count = serializers.IntegerField(read_only=True)
    team_age_days   = serializers.SerializerMethodField()
    logo_url        = serializers.SerializerMethodField()

    class Meta:
        model  = Team
        fields = [
            'id', 'name',
            'goals_scored', 'total_wins', 'total_losses',
            'avg_player_age', 'active_member_count',
            'team_age_days', 'logo_url',
        ]

    def get_team_age_days(self, obj) -> int:
        return (timezone.now() - obj.created_at).days

    def get_logo_url(self, obj) -> str | None:
        try:
            request = self.context['request']
            return request.build_absolute_uri(obj.logo.logo.url)
        except (AttributeError, ValueError):
            return None