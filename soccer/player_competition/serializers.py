from django.utils import timezone
from rest_framework import serializers
from player_team.models import Team, TeamMember
from player_booking.models import BookingStatus
from .models import Challenge, ChallengePlayerBooking, ScoreSubmission, ChallengeStatus
from datetime import date, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from collections import Counter
from django.db import transaction

import datetime
from django.utils import timezone as tz

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



def _resolve_result(
    status,
    result_team,
    result_challenged_team,
    is_our_team_first: bool,
    date: datetime.date,
    end_time: datetime.time,
    score_finalized,

) -> str | None:

    # Check if the challenge hasn't finished yet
    end_naive = datetime.datetime.combine(date, end_time)
    end_dt = tz.make_aware(end_naive) if tz.is_naive(end_naive) else end_naive
    if (not score_finalized)  and end_dt > tz.now():
        return 'قريباً'
    if (not score_finalized) and (not end_dt > tz.now()):
        return 'لم_يتم_التصويت'

    our_score, their_score = (
        (result_team, result_challenged_team) if is_our_team_first
        else (result_challenged_team, result_team)
    )
    if our_score > their_score: return 'فوز'
    if our_score < their_score: return 'خسارة'
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
            status                 = obj.status,
            result_team            = obj.result_team,
            result_challenged_team = obj.result_challenged_team,
            is_our_team_first      = str(obj.team_id) == self._team_id(),
            date                   = obj.date,
            end_time               = obj.end_time,
            score_finalized        = obj.score_finalized,

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
            status                 = obj.challenge.status,
            result_team            = obj.challenge.result_team,
            result_challenged_team = obj.challenge.result_challenged_team,
            is_our_team_first      = obj.team_id == obj.challenge.team_id,
            date                   = obj.challenge.date,
            end_time               = obj.challenge.end_time,
            score_finalized        = obj.challenge.score_finalized,
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
            'created_at',
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
    id             = serializers.UUIDField(read_only=True)
    date           = serializers.DateField(read_only=True)
    start_time     = serializers.TimeField(read_only=True)
    end_time       = serializers.TimeField(read_only=True)
    my_score       = serializers.SerializerMethodField()
    opponent_score = serializers.SerializerMethodField()
    opponent       = serializers.SerializerMethodField()
    challenge_status = serializers.SerializerMethodField()   # ← new

    def _is_sent(self, obj) -> bool:
        return str(obj.team_id) == str(self.context['team_id'])

    def get_my_score(self, obj):
        return obj.result_team if self._is_sent(obj) else obj.result_challenged_team

    def get_opponent_score(self, obj):
        return obj.result_challenged_team if self._is_sent(obj) else obj.result_team

    def get_opponent(self, obj):
        opponent = obj.challenged_team if self._is_sent(obj) else obj.team
        return VSTeamSerializer(opponent, context=self.context).data

    def get_challenge_status(self, obj):
        end_naive = datetime.datetime.combine(obj.date, obj.end_time)
        end_dt = tz.make_aware(end_naive) if tz.is_naive(end_naive) else end_naive
      
        if not obj.score_finalized:
            return 'قريباً'
        if (not obj.score_finalized) and (not end_dt > tz.now()):
            return 'لم_يتم_التصويت'

        my_score  = self.get_my_score(obj)
        opp_score = self.get_opponent_score(obj)

        if my_score is None or opp_score is None:
            return None  # time passed but result not recorded yet

        if my_score > opp_score:
            return 'فوز'
        if my_score < opp_score:
            return 'خسارة'
        return 'تعادل'

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
    governorate    = serializers.CharField(source='get_governorate_display')


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
            'governorate'
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
    id                     = serializers.UUIDField(source='challenge.id',                        read_only=True)
    date                   = serializers.DateField(source='challenge.date',                      read_only=True)
    start_time             = serializers.CharField(source='challenge.start_time',                read_only=True)
    end_time               = serializers.CharField(source='challenge.end_time',                  read_only=True)
    result_team            = serializers.IntegerField(source='challenge.result_team',            read_only=True)
    result_challenged_team = serializers.IntegerField(source='challenge.result_challenged_team', read_only=True)
    team                   = serializers.SerializerMethodField()
    challenged_team        = serializers.SerializerMethodField()
    player_team_id         = serializers.UUIDField(source='team_id',                            read_only=True)
    player_side            = serializers.SerializerMethodField()
    challenge_status       = serializers.SerializerMethodField()   # ← new

    def get_team(self, obj):
        return TeamInPlayerChallengeSerializer(obj.challenge.team, context=self.context).data

    def get_challenged_team(self, obj):
        return TeamInPlayerChallengeSerializer(obj.challenge.challenged_team, context=self.context).data

    def get_player_side(self, obj):
        if obj.team_id == obj.challenge.team_id:
            return 'team'
        elif obj.team_id == obj.challenge.challenged_team_id:
            return 'challenged_team'
        return None

    def get_challenge_status(self, obj):
        challenge = obj.challenge
        end_naive = datetime.datetime.combine(challenge.date, challenge.end_time)
        end_dt = tz.make_aware(end_naive) if tz.is_naive(end_naive) else end_naive
        if not challenge.score_finalized:
            return 'قريباً'
        if (not challenge.score_finalized) and (not end_dt > tz.now()):
            return 'لم_يتم_التصويت'

        # Resolve scores from the player's perspective
        if obj.team_id == challenge.team_id:
            my_score, opp_score = challenge.result_team, challenge.result_challenged_team
        else:
            my_score, opp_score = challenge.result_challenged_team, challenge.result_team

        if my_score is None or opp_score is None:
            return None   # result not recorded yet despite time passing

        if my_score > opp_score:
            return 'فوز'
        if my_score < opp_score:
            return 'خسارة'
        return 'تعادل'


class ScoreSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ScoreSubmission
        fields = ['challenge', 'result_team', 'result_challenged_team']

    def validate(self, attrs):
        challenge = attrs['challenge']
        player    = self.context['request'].user

        # check booking is completed first
        if challenge.booking is None:
            raise serializers.ValidationError('لا يوجد حجز مرتبط بهذه المباراة.')
        
        if challenge.booking.status != BookingStatus.COMPLETED:
            raise serializers.ValidationError('لا يمكن إرسال النتيجة قبل اكتمال الحجز.')

        # check player participated in this challenge
        participated = ChallengePlayerBooking.objects.filter(
            challenge=challenge,
            player=player
        ).exists()
        if not participated:
            raise serializers.ValidationError('لم تشارك في هذه المباراة.')

        # check already submitted
        already_submitted = ScoreSubmission.objects.filter(
            challenge=challenge,
            player=player
        ).exists()
        if already_submitted:
            raise serializers.ValidationError('لقد قمت بإرسال النتيجة مسبقاً.')

        return attrs


    def create(self, validated_data):
        challenge = validated_data['challenge']
        player    = self.context['request'].user
        
        with transaction.atomic():
            # save submission
            submission = ScoreSubmission.objects.create(
                challenge=challenge,
                player=player,
                result_team=validated_data['result_team'],
                result_challenged_team=validated_data['result_challenged_team'],
            )

            ChallengePlayerBooking.objects.filter(challenge=challenge, player=player).update(score_done=True)

            # check if we can decide the final score
            self._try_finalize_score(challenge)

        return submission

    def _try_finalize_score(self, challenge):
        
        # get total players count
        total_players = ChallengePlayerBooking.objects.filter(
            challenge=challenge
        ).count()

        # get all submissions
        submissions = ScoreSubmission.objects.filter(challenge=challenge)
        submitted_count = submissions.count()

        print(f'[score] {submitted_count}/{total_players} submitted')

        # count votes per score combination
        votes = Counter(
            (s.result_team, s.result_challenged_team)
            for s in submissions
        )

        majority_threshold = total_players / 2
        most_common_score, most_common_count = votes.most_common(1)[0]

        if most_common_count > majority_threshold:
            # majority reached → finalize immediately
            challenge.result_team            = most_common_score[0]
            challenge.result_challenged_team = most_common_score[1]
            challenge.status                 = ChallengeStatus.ACCEPTED
            challenge.score_finalized        = True
            challenge.save(update_fields=['result_team', 'result_challenged_team', 'status', 'score_finalized'])
            print(f'[score] majority agreed: {most_common_score[0]}-{most_common_score[1]} ✅')
            return  # ← stop here, don't continue

        if submitted_count == total_players:
            # all submitted but no majority → 50/50 split
            challenge.status = ChallengeStatus.DISPUTED_SCORE
            challenge.score_finalized = True
            challenge.save(update_fields=['status', 'score_finalized'])
            print(f'[score] 50/50 split, no majority ✅')
            return

        # not enough submissions yet
        print(f'[score] no majority yet, waiting...')


class PlayerProfileSerializer(serializers.ModelSerializer):
    age            = serializers.IntegerField(read_only=True)
    image          = serializers.SerializerMethodField()
    challenges     = serializers.SerializerMethodField()
    negative_time  = serializers.SerializerMethodField()
    in_team        = serializers.SerializerMethodField()   
    request_id     = serializers.SerializerMethodField()
    governorate = serializers.CharField(source='get_governorate_display')
   

    class Meta:
        model  = User
        fields = [
            'id', 'full_name', 'username', 'image',
            'age', 'height', 'weight', 'foot_preference',
            'booking_time', 'challenge_time',
            'negative_time',
            'challenge_wins', 'challenge_losses', 'challenge_draw',

            'in_team',      # null when team_id not supplied
            'request_id',   # null when team_id not supplied or no pending invite
            'challenges',
            'governorate'
        ]

    def get_negative_time(self, obj):
        return (
            getattr(obj, 'cancel_time',   0) +
            getattr(obj, 'no_show_time',  0) +
            getattr(obj, 'disputed_time', 0) +
            getattr(obj, 'expired_time', 0)
        )

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.image:
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None

    def get_challenges(self, obj):
        played = getattr(obj, 'played_challenges', [])
        return PlayerChallengeSerializer(played, many=True, context=self.context).data

    # Pull straight from context — no extra DB work here
    def get_in_team(self, obj):
        return self.context.get('in_team')   # None if team_id wasn't supplied

    def get_request_id(self, obj):
        return self.context.get('request_id')
   

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
    deposit = serializers.UUIDField(required=False)


    def validate_date(self, value):
        today = tz.localtime(timezone.now()).date()
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
    governorate = serializers.CharField(source='get_governorate_display')


    class Meta:
        model  = Team
        fields = [
            'id', 'name',
            'goals_scored', 'total_wins', 'total_losses',
            'avg_player_age', 'active_member_count',
            'team_age_days', 'logo_url', 'governorate'
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
    governorate = serializers.CharField(source='get_governorate_display')


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