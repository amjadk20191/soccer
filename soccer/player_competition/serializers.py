from django.utils import timezone
from rest_framework import serializers
from player_team.models import Team, TeamMember
from .models import Challenge, ChallengePlayerBooking, ChallengeStatus
from datetime import date, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()



class TeamSnippetSerializer(serializers.Serializer):
    id   = serializers.UUIDField()
    name = serializers.CharField()
    logo = serializers.SerializerMethodField()

    def get_logo(self, obj):
        request = self.context.get('request')
        if obj.logo and obj.logo.logo:
            return request.build_absolute_uri(obj.logo.logo.url) if request else obj.logo.logo.url
        return None

def _resolve_result(status, result_team, result_challenged_team, is_our_team_first: bool) -> str | None:
    status_map = {
        ChallengeStatus.CANCELED:       'ملغى',
        ChallengeStatus.NO_SHOW:        'لم يحضر',
        ChallengeStatus.DISPUTED_SCORE: 'مشكلة في النتيجة',
        ChallengeStatus.DISPUTED:       'مشكلة',
    }
    if status in status_map:
        return status_map[status]

    if result_team is None or result_challenged_team is None:
        return 'قريبا'   # ← ACCEPTED but no scores yet

    our_score, their_score = (
        (result_team, result_challenged_team) if is_our_team_first
        else (result_challenged_team, result_team)
    )
    if our_score > their_score: return 'فاز'
    if our_score < their_score: return 'خسر'
    return 'تعادل'


class TeamChallengeSerializer(serializers.ModelSerializer):
    """For team-scoped challenge list — perspective relative to the requested team."""
    team            = TeamSnippetSerializer(read_only=True)
    challenged_team = TeamSnippetSerializer(read_only=True)
    team_side       = serializers.SerializerMethodField()  # 'team' | 'challenged_team'
    result          = serializers.SerializerMethodField()  # 'won' | 'lost' | 'drawn'

    class Meta:
        model  = Challenge
        fields = [
            'id', 'date', 'start_time', 'end_time',
            'result_team', 'result_challenged_team',
            'team', 'challenged_team',
            'team_side', 'result',
        ]

    def _team_id(self):
        return str(self.context.get('team_id', ''))

    def get_team_side(self, obj):
        return 'team' if str(obj.team_id) == self._team_id() else 'challenged_team'

    def get_result(self, obj):
        return _resolve_result(
            status                   = obj.status,
            result_team              = obj.result_team,
            result_challenged_team   = obj.result_challenged_team,
            is_our_team_first        = str(obj.team_id) == self._team_id(),
        )


class PlayerChallengeListSerializer(serializers.Serializer):
    """For player-scoped challenge list — perspective relative to the player's team side."""
    id                     = serializers.UUIDField(source='challenge.id')
    date                   = serializers.DateField(source='challenge.date')
    start_time             = serializers.TimeField(source='challenge.start_time')
    end_time               = serializers.TimeField(source='challenge.end_time')
    result_team            = serializers.IntegerField(source='challenge.result_team',            allow_null=True)
    result_challenged_team = serializers.IntegerField(source='challenge.result_challenged_team', allow_null=True)
    team                   = serializers.SerializerMethodField()
    challenged_team        = serializers.SerializerMethodField()
    player_side            = serializers.SerializerMethodField()
    result                 = serializers.SerializerMethodField()

    def get_team(self, obj):
        return TeamSnippetSerializer(obj.challenge.team, context=self.context).data

    def get_challenged_team(self, obj):
        return TeamSnippetSerializer(obj.challenge.challenged_team, context=self.context).data

    def get_player_side(self, obj):
        if obj.team_id == obj.challenge.team_id:
            return 'team'
        elif obj.team_id == obj.challenge.challenged_team_id:
            return 'challenged_team'
        return None

    def get_result(self, obj):
        return _resolve_result(
            status                   = obj.challenge.status,
            result_team              = obj.challenge.result_team,
            result_challenged_team   = obj.challenge.result_challenged_team,
            is_our_team_first        = obj.team_id == obj.challenge.team_id,
        )

class PitchSerializer(serializers.Serializer):
    id   = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)


class ClubSerializer(serializers.Serializer):
    id   = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)


class PlayerSerializer(serializers.Serializer):
    id        = serializers.UUIDField(source='player.id',        read_only=True)
    full_name = serializers.CharField(source='player.full_name', read_only=True)
    username  = serializers.CharField(source='player.username',  read_only=True)
    image     = serializers.SerializerMethodField()

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.player.image:
            return request.build_absolute_uri(obj.player.image.url) if request else obj.player.image.url
        return None


class TeamWithPlayersSerializer(serializers.Serializer):
    id      = serializers.UUIDField(read_only=True)
    name    = serializers.CharField(read_only=True)
    logo    = serializers.SerializerMethodField()
    players = serializers.SerializerMethodField()

    def get_logo(self, obj):
        request = self.context.get('request')
        if obj.logo and obj.logo.logo:
            return request.build_absolute_uri(obj.logo.logo.url) if request else obj.logo.logo.url
        return None

    def get_players(self, obj):
        # Read from grouped dict injected via context — zero DB hit
        team_players = self.context.get('team_players', {})
        players      = team_players.get(str(obj.id), [])
        return PlayerSerializer(players, many=True, context=self.context).data


class ChallengeDetailSerializer(serializers.ModelSerializer):
    pitch           = PitchSerializer(read_only=True)
    club            = ClubSerializer(read_only=True)
    team            = serializers.SerializerMethodField()
    challenged_team = serializers.SerializerMethodField()

    class Meta:
        model  = Challenge
        fields = [
            'id',
            'date',
            'start_time',
            'end_time',
            'result_team',
            'result_challenged_team',
            'pitch',
            'club',
            'team',
            'challenged_team',
        ]

    def _team_players_context(self, obj):
        # Group prefetched players by team_id once — reused for both teams
        if 'team_players' not in self.context:
            team_players = {}
            for cp in getattr(obj, 'challenge_players', []):
                team_players.setdefault(str(cp.team_id), []).append(cp)
            self.context['team_players'] = team_players
        return self.context

    def get_team(self, obj):
        return TeamWithPlayersSerializer(
            obj.team, context=self._team_players_context(obj)
        ).data

    def get_challenged_team(self, obj):
        return TeamWithPlayersSerializer(
            obj.challenged_team, context=self._team_players_context(obj)
        ).data
    

class TeamLogoMixin:
    """Reusable logo resolver"""
    def get_logo(self, obj):
        request = self.context.get('request')
        logo = getattr(obj, 'logo', None)
        if logo and logo.logo:
            return request.build_absolute_uri(logo.logo.url) if request else logo.logo.url
        return None


class PlayerInTeamSerializer(serializers.Serializer):
    id              = serializers.UUIDField(source='player.id',                      read_only=True)
    full_name       = serializers.CharField(source='player.full_name',               read_only=True)
    username        = serializers.CharField(source='player.username',                read_only=True)
    is_captain      = serializers.BooleanField(read_only=True)
    joined_at       = serializers.DateTimeField(format="%Y-%m-%d", read_only=True)
    image           = serializers.SerializerMethodField()

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.player.image:
            return request.build_absolute_uri(obj.player.image.url) if request else obj.player.image.url
        return None


class VSTeamSerializer(TeamLogoMixin, serializers.Serializer):
    """Minimal opponent team info for challenge history"""
    id   = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    logo = serializers.SerializerMethodField()


class ChallengeHistorySerializer(serializers.Serializer):
    """
    Unified shape for both sent and received challenges.
    `my_score` and `opponent_score` are resolved relative to the team being viewed.
    """
    id             = serializers.UUIDField(read_only=True)
    date           = serializers.DateField(read_only=True)
    start_time     = serializers.TimeField(read_only=True)
    end_time       = serializers.TimeField(read_only=True)
    my_score       = serializers.SerializerMethodField()
    opponent_score = serializers.SerializerMethodField()
    opponent       = serializers.SerializerMethodField()

    def _is_sent(self, obj) -> bool:
        """True if the viewed team was the challenger (team), False if challenged"""
        return str(obj.team_id) == str(self.context['team_id'])

    def get_my_score(self, obj):
        return obj.result_team if self._is_sent(obj) else obj.result_challenged_team

    def get_opponent_score(self, obj):
        return obj.result_challenged_team if self._is_sent(obj) else obj.result_team

    def get_opponent(self, obj):
        opponent = obj.challenged_team if self._is_sent(obj) else obj.team
        return VSTeamSerializer(opponent, context=self.context).data


class TeamStatisticsSerializer(serializers.Serializer):
    total_wins      = serializers.IntegerField(read_only=True)
    total_losses    = serializers.IntegerField(read_only=True)
    total_draw      = serializers.IntegerField(read_only=True)
    total_canceled  = serializers.IntegerField(read_only=True)
    total_matches   = serializers.IntegerField(read_only=True)
    win_rate        = serializers.FloatField(read_only=True)
    goals_scored    = serializers.IntegerField(read_only=True)
    goals_conceded  = serializers.IntegerField(read_only=True)
    clean_sheet     = serializers.IntegerField(read_only=True)
    failed_to_score = serializers.IntegerField(read_only=True)


class TeamDetailSerializer(TeamLogoMixin, serializers.ModelSerializer):
    logo           = serializers.SerializerMethodField()
    statistics     = serializers.SerializerMethodField()
    active_players = serializers.SerializerMethodField()
    challenges     = serializers.SerializerMethodField()
    total_players  = serializers.SerializerMethodField()

    class Meta:
        model  = Team
        fields = [
            'id',
            'name',
            'logo',
            'address',
            'time',
            'total_players',
            'statistics',
            'active_players',
            'challenges',
        ]

    def get_statistics(self, obj):
        return TeamStatisticsSerializer(obj).data

    def get_total_players(self, obj):
        return len(getattr(obj, 'active_members', []))

    def get_active_players(self, obj):
        members = getattr(obj, 'active_members', [])
        return PlayerInTeamSerializer(members, many=True, context=self.context).data

    def get_challenges(self, obj):
        # Merge sent + received — already prefetched, pure Python
        context = {**self.context, 'team_id': str(obj.id)}

        sent     = getattr(obj, 'sent_challenges',     [])
        received = getattr(obj, 'received_challenges', [])
        all_challenges = sorted(
            sent + received,
            key=lambda c: c.date,
            reverse=True,
        )
        return ChallengeHistorySerializer(all_challenges, many=True, context=context).data


class TeamInPlayerChallengeSerializer(serializers.Serializer):
    id   = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    logo = serializers.SerializerMethodField()

    def get_logo(self, obj):
        request = self.context.get('request')
        if obj.logo and obj.logo.logo:
            return request.build_absolute_uri(obj.logo.logo.url) if request else obj.logo.logo.url
        return None


class PlayerChallengeSerializer(serializers.Serializer):
    """Represents a single challenge the player participated in"""
    id                       = serializers.UUIDField(source='challenge.id',                       read_only=True)
    date                     = serializers.DateField(source='challenge.date',                     read_only=True)
    start_time                   = serializers.CharField(source='challenge.start_time',       read_only=True)
    end_time                   = serializers.CharField(source='challenge.end_time',       read_only=True)
    result_team              = serializers.IntegerField(source='challenge.result_team',           read_only=True)
    result_challenged_team   = serializers.IntegerField(source='challenge.result_challenged_team',read_only=True)
    team                     = serializers.SerializerMethodField()
    challenged_team          = serializers.SerializerMethodField()
    player_team_id           = serializers.UUIDField(source='team_id', read_only=True)  # which side the player was on
    player_side        = serializers.SerializerMethodField()

    def get_team(self, obj):
        return TeamInPlayerChallengeSerializer(
            obj.challenge.team, context=self.context
        ).data

    def get_challenged_team(self, obj):
        return TeamInPlayerChallengeSerializer(
            obj.challenge.challenged_team, context=self.context
        ).data

    def get_player_side(self, obj):
        # obj.team_id  → the team this player was registered under in ChallengePlayerBooking
        # compare against the challenge's two sides
        if obj.team_id == obj.challenge.team_id:
            return 'team'
        elif obj.team_id == obj.challenge.challenged_team_id:
            return 'challenged_team'
        return None  # shouldn't happen, but safe fallback


class PlayerProfileSerializer(serializers.ModelSerializer):
    # foot_preference_display    = serializers.CharField(source='get_foot_preference_display', read_only=True)
    # foot_preference    = serializers.CharField(source='get_foot_preference', read_only=True)
    age                = serializers.IntegerField(read_only=True)
    image              = serializers.SerializerMethodField()
    challenges         = serializers.SerializerMethodField()
    negative_time      = serializers.SerializerMethodField()



    class Meta:
        model  = User
        fields = [
            'id',
            'full_name',
            'username',
            'image',
            'age',
            'height',
            'weight',
            'foot_preference',
            'booking_time',
            'challenge_time',
            'negative_time',
            'challenges',
        ]
    
    def get_negative_time(self, obj):
        return (
            getattr(obj, 'cancel_time',   0) +
            getattr(obj, 'no_show_time',  0) +
            getattr(obj, 'disputed_time', 0)
        )
    
    def get_image(self, obj):
        request = self.context.get('request')
        if obj.image:
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None

    def get_challenges(self, obj):
        played = getattr(obj, 'played_challenges', [])
        return PlayerChallengeSerializer(played, many=True, context=self.context).data

   

class CreateChallengeEquipmentsSerializer(serializers.Serializer):
    id = serializers.UUIDField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل معرّف UUID صحيح.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    quantity = serializers.IntegerField(
        min_value=1,
        error_messages={
            'required':  'هذا الحقل مطلوب.',
            'invalid':   'أدخل عدداً صحيحاً.',
            'min_value': 'يجب أن تكون الكمية 1 على الأقل.',
        }

    )

class CreateChallengeSerializer(serializers.Serializer):
    team_id = serializers.UUIDField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل معرّف UUID صحيح.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    challenged_team_id = serializers.UUIDField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل معرّف UUID صحيح.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    pitch_id = serializers.UUIDField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل معرّف UUID صحيح.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    club_id = serializers.UUIDField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل معرّف UUID صحيح.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    start_time = serializers.TimeField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل وقتاً صحيحاً.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    end_time = serializers.TimeField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل وقتاً صحيحاً.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    date = serializers.DateField(
        error_messages={
            'required': 'هذا الحقل مطلوب.',
            'invalid':  'أدخل تاريخاً صحيحاً.',
            'null':     'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )
    equipments = CreateChallengeEquipmentsSerializer(many=True, required=False)


    def validate_date(self, value):
        today = date.today()
        print(today)
        if not (today + timedelta(days=settings.MIN_NUM_DAY_BEFORE_CHALLENGE) <= value <= today + timedelta(days=settings.MAX_NUM_DAY_BEFORE_CHALLENGE)):
            raise serializers.ValidationError({"error": f'تاريخ التحدي يجب أن يكون بين {settings.MIN_NUM_DAY_BEFORE_CHALLENGE} و {settings.MAX_NUM_DAY_BEFORE_CHALLENGE} يومًا من اليوم.'})
        return value

    def validate(self, attrs):
        if attrs['team_id'] == attrs['challenged_team_id']:
            raise serializers.ValidationError({"error": "لا يمكن تحدي الفريق لنفسه."})
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError({"error": "وقت النهاية يجب أن يكون بعد وقت البداية."})
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


# ── Output ─────────────────────────────────────────────────────────────────────
class TeamBriefSerializer(serializers.Serializer):
    """Minimal team representation — no extra DB hit (data already select_related)."""
    id             = serializers.UUIDField()
    name           = serializers.CharField()
    total_wins     = serializers.IntegerField()
    total_losses   = serializers.IntegerField()
    total_canceled = serializers.IntegerField()
    goals_scored   = serializers.IntegerField()
    clean_sheet    = serializers.IntegerField()
    logo           = serializers.SerializerMethodField()

    def get_logo(self, obj) -> str | None:
        request = self.context.get("request")
        image_field = obj.logo.logo          # Team.logo → TeamImage.logo (ImageField)
        if not image_field:
            return None
        return request.build_absolute_uri(image_field.url) if request else image_field.url


class PitchBriefSerializer(serializers.Serializer):
    id   = serializers.UUIDField()
    name = serializers.CharField()


class ClubBriefSerializer(serializers.Serializer):
    id   = serializers.UUIDField()
    name = serializers.CharField()


class ChallengeEquipmentSerializer(serializers.Serializer):
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    quantity = serializers.IntegerField()

    def get_name(self, obj):
        return obj.equipment.equipment.name

    def get_description(self, obj):
        return obj.equipment.equipment.description

    def get_image(self, obj):
        request = self.context.get("request")
        image_field = obj.equipment.equipment.image

        if not image_field:
            return None

        return request.build_absolute_uri(image_field.url) if request else image_field.url

class PendingChallengeSerializer(serializers.ModelSerializer):
    team            = TeamBriefSerializer(read_only=True)
    pitch           = PitchBriefSerializer(read_only=True)
    club            = ClubBriefSerializer(read_only=True)
    equipment       = ChallengeEquipmentSerializer(read_only=True, many=True, source='challengeequipment_set')

    class Meta:
        model  = Challenge
        fields = [
            "id",
            "team",
            "pitch",
            "club",
            "date",
            "start_time",
            "end_time",
            "equipment"
        ]


class RequestedChallengeSerializer(serializers.ModelSerializer):
    challenged_team = TeamBriefSerializer(read_only=True)
    pitch           = PitchBriefSerializer(read_only=True)
    club            = ClubBriefSerializer(read_only=True)
    equipment       = ChallengeEquipmentSerializer(read_only=True, many=True, source='challengeequipment_set')


    class Meta:
        model  = Challenge
        fields = [
            "id",
            "challenged_team",
            "pitch",
            "club",
            "date",
            "start_time",
            "end_time",
            "equipment"
        ]

# ── Input ──────────────────────────────────────────────────────────────────────

class ChallengeReplySerializer(serializers.Serializer):
    class Action(serializers.ChoiceField):
        pass

    ACCEPT = "accept"
    REJECT = "reject"

    action = serializers.ChoiceField(
        choices=[ACCEPT, REJECT],
        error_messages={
            'required':       'هذا الحقل مطلوب.',
            'invalid_choice': 'القيمة "{input}" غير صحيحة. الخيارات المتاحة: accept, reject.',
            'null':           'لا يمكن أن تكون هذه القيمة فارغة.',
        }
    )