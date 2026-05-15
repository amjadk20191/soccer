# player_competition/signals/signals_challenge_result.py

from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from player_competition.models import Challenge, ChallengePlayerBooking


@receiver(pre_save, sender=Challenge)
def update_team_stats_on_result(sender, instance, **kwargs):
    if not instance.pk:
        return

    try:
        old = Challenge.objects.get(pk=instance.pk)
    except Challenge.DoesNotExist:
        return

    # only fire when result actually changed
    if old.result_team == instance.result_team and old.result_challenged_team == instance.result_challenged_team:
        if old.score_finalized == instance.score_finalized:
            return  # nothing changed at all, skip

    from player_team.models import Team
    from core.models import User

    team            = Team.objects.get(pk=instance.team_id)
    challenged_team = Team.objects.get(pk=instance.challenged_team_id)

    # ── UNDO old stats if previous score was not 0-0 ─────────
    old_score_team       = old.result_team
    old_score_challenged = old.result_challenged_team

    if not (old_score_team == 0 and old_score_challenged == 0):
        print(f'[team_stats] undoing old score {old_score_team}-{old_score_challenged}')

        # undo goals
        team.goals_scored   -= old_score_team
        team.goals_conceded -= old_score_challenged

        challenged_team.goals_scored   -= old_score_challenged
        challenged_team.goals_conceded -= old_score_team

        # undo win/loss/draw
        if old_score_team > old_score_challenged:
            team.total_wins              -= 1
            challenged_team.total_losses -= 1
            old_winning_team_id = team.id

        elif old_score_challenged > old_score_team:
            challenged_team.total_wins -= 1
            team.total_losses          -= 1
            old_winning_team_id = challenged_team.id

        else:
            team.total_draw            -= 1
            challenged_team.total_draw -= 1
            old_winning_team_id = None

        # undo clean sheet
        if old_score_challenged == 0:
            team.clean_sheet -= 1

        if old_score_team == 0:
            challenged_team.clean_sheet -= 1

        # undo failed to score
        if old_score_team == 0:
            team.failed_to_score -= 1

        if old_score_challenged == 0:
            challenged_team.failed_to_score -= 1

        # undo player stats
        if old_winning_team_id:
            old_losing_team_id = (
                challenged_team.id if old_winning_team_id == team.id else team.id
            )

            old_winning_player_ids = ChallengePlayerBooking.objects.filter(
                challenge=instance,
                team_id=old_winning_team_id,
            ).values_list('player_id', flat=True)

            old_losing_player_ids = ChallengePlayerBooking.objects.filter(
                challenge=instance,
                team_id=old_losing_team_id,
            ).values_list('player_id', flat=True)

            User.objects.filter(id__in=old_winning_player_ids).update(
                challenge_wins=models.F('challenge_wins') - 1
            )
            User.objects.filter(id__in=old_losing_player_ids).update(
                challenge_losses=models.F('challenge_losses') - 1
            )
            print(f'[player_stats] undid wins/losses for challenge {instance.id}')

        else:
            # old was a draw — undo draw for all players
            all_old_player_ids = ChallengePlayerBooking.objects.filter(
                challenge=instance,
            ).values_list('player_id', flat=True)

            User.objects.filter(id__in=all_old_player_ids).update(
                challenge_draw=models.F('challenge_draw') - 1
            )
            print(f'[player_stats] undid draws for challenge {instance.id}')

    # ── ADD new stats ─────────────────────────────────────────
    score_team       = instance.result_team
    score_challenged = instance.result_challenged_team

    print(f'[team_stats] adding new score {score_team}-{score_challenged}')

    # goals
    team.goals_scored   += score_team
    team.goals_conceded += score_challenged

    challenged_team.goals_scored   += score_challenged
    challenged_team.goals_conceded += score_team

    # win/loss/draw
    if score_team > score_challenged:
        team.total_wins              += 1
        challenged_team.total_losses += 1
        winning_team_id = team.id

    elif score_challenged > score_team:
        challenged_team.total_wins += 1
        team.total_losses          += 1
        winning_team_id = challenged_team.id

    else:
        team.total_draw            += 1
        challenged_team.total_draw += 1
        winning_team_id = None

    # clean sheet
    if score_challenged == 0:
        team.clean_sheet += 1

    if score_team == 0:
        challenged_team.clean_sheet += 1

    # failed to score
    if score_team == 0:
        team.failed_to_score += 1

    if score_challenged == 0:
        challenged_team.failed_to_score += 1

    # ── Save both teams ───────────────────────────────────────
    team.save(update_fields=[
        'total_wins', 'total_losses', 'total_draw',
        'goals_scored', 'goals_conceded',
        'clean_sheet', 'failed_to_score',
    ])
    challenged_team.save(update_fields=[
        'total_wins', 'total_losses', 'total_draw',
        'goals_scored', 'goals_conceded',
        'clean_sheet', 'failed_to_score',
    ])

    print(f'[team_stats] team:      wins={team.total_wins} losses={team.total_losses} goals={team.goals_scored}-{team.goals_conceded}')
    print(f'[team_stats] challenged: wins={challenged_team.total_wins} losses={challenged_team.total_losses} goals={challenged_team.goals_scored}-{challenged_team.goals_conceded}')

    # ── Update player stats for new result ───────────────────
    if winning_team_id:
        losing_team_id = (
            challenged_team.id if winning_team_id == team.id else team.id
        )

        winning_player_ids = ChallengePlayerBooking.objects.filter(
            challenge=instance,
            team_id=winning_team_id,
        ).values_list('player_id', flat=True)

        losing_player_ids = ChallengePlayerBooking.objects.filter(
            challenge=instance,
            team_id=losing_team_id,
        ).values_list('player_id', flat=True)

        User.objects.filter(id__in=winning_player_ids).update(
            challenge_wins=models.F('challenge_wins') + 1
        )
        User.objects.filter(id__in=losing_player_ids).update(
            challenge_losses=models.F('challenge_losses') + 1
        )
        print(f'[player_stats] updated wins/losses for challenge {instance.id} ✅')

    else:
        # draw — update all players in the challenge
        all_player_ids = ChallengePlayerBooking.objects.filter(
            challenge=instance,
        ).values_list('player_id', flat=True)

        User.objects.filter(id__in=all_player_ids).update(
            challenge_draw=models.F('challenge_draw') + 1
        )
        print(f'[player_stats] updated draws for challenge {instance.id} ✅')

    print(f'[team_stats] updated stats for challenge {instance.id} ✅')