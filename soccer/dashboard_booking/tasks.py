from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q
from player_booking.models import Booking, BookingStatus, Review
from core.models import User
from core.services.notification_service import NotificationService
from player_competition.models import ChallengePlayerBooking, Challenge, ChallengeStatus
from django.db import models
from django.db.models import F, ExpressionWrapper, DateTimeField
from dashboard_booking.models import BookingNotification

# ── shared helper ─────────────────────────────────────────────────────────────

def _get_club_workers(club_id):
    """Returns manager + all staff for a club as a queryset."""
    return User.objects.filter(
        Q(club__id=club_id) |         # manager  (related_name="club")
        Q(clubstaff__club_id=club_id) # staff
    ).distinct()


def _notify_club_workers(club, title, body, notification_type, helper_id):
    """Send the same notification to every worker (manager + staff) of a club."""
    if not club:
        return
    for worker in _get_club_workers(club.id):
        try:
            NotificationService.send_notification(
                user=worker,
                title=title,
                body=body,
                notification_type=notification_type,
                helper_id=helper_id,
            )
        except Exception as e:
            print(f'  club worker {worker} notification failed: {e}')


# ── tasks ─────────────────────────────────────────────────────────────────────

def remind_owner_before_booking():
    now = timezone.localtime(timezone.now())
    today = now.date()

    time_start = (now + timedelta(minutes=120)).time()
    time_end   = (now + timedelta(minutes=200)).time()

    bookings = Booking.objects.filter(
        date=today,
        start_time__gte=time_start,
        start_time__lte=time_end,
        owner_reminded=False,
        status__in=[
            BookingStatus.PENDING_PAY,
            BookingStatus.COMPLETED,
        ]
    ).select_related('club__manager', 'player', 'pitch')

    for booking in bookings:
        player     = booking.player
        pitch_name = booking.pitch.name if hasattr(booking.pitch, 'name') else 'الملعب'
        start_str  = booking.start_time.strftime('%H:%M')
        player_name = player.full_name if player else 'لاعب'

        # ── Notify all club workers (manager + staff) ──────────────
        _notify_club_workers(
            club=booking.club,
            title='تذكير بحجز قادم',
            body=f'لديك حجز في {pitch_name} الساعة {start_str} من {player_name}',
            notification_type='booking_reminder',
            helper_id=booking.id,
        )

        # ── Notify player ──────────────────────────────────────────
        if player:
            try:
                NotificationService.send_notification(
                    user=player,
                    title='تذكير بحجزك',
                    body=f'حجزك في {pitch_name} سيبدأ الساعة {start_str}، استعد!',
                    notification_type='booking_reminder',
                    helper_id=booking.id,
                )
            except Exception as e:
                print(f'  player notification failed: {e}')

        booking.owner_reminded = True
        booking.save(update_fields=['owner_reminded'])


def notify_players_to_rate():
    """
    Runs every 5 minutes.
    Finds completed bookings where end_time has passed.
    Regular booking  → notify the player who booked.
    Challenge booking → notify all players in ChallengePlayerBooking.
    """
    now      = timezone.localtime(timezone.now())
    today    = now.date()
    now_time = now.time()

    bookings = Booking.objects.filter(
        date=today,
        end_time__lte=now_time,
        rate_notified=False,
        status=BookingStatus.COMPLETED,
    ).select_related('player', 'pitch', 'club')

    print(f'[rate_notify] found {bookings.count()} bookings')

    for booking in bookings:
        pitch_name = booking.pitch.name if hasattr(booking.pitch, 'name') else 'الملعب'

        if booking.is_challenge:
            challenge_players = ChallengePlayerBooking.objects.filter(
                booking=booking
            ).select_related('player')

            print(f'  challenge booking {booking.id} → {challenge_players.count()} players')

            for cp in challenge_players:
                player = cp.player
                if Review.objects.filter(booking=booking, player=player).exists():
                    print(f'    player {player} already rated, skip')
                    continue
                try:
                    NotificationService.send_notification(
                        user=player,
                        title='قيّم الملعب',
                        body=f'كيف كانت تجربتك في {pitch_name}؟ قيّم الملعب الآن!',
                        notification_type='rate_pitch',
                        helper_id=booking.id,
                    )
                    print(f'    player {player} notified ✅')
                except Exception as e:
                    print(f'    player {player} notification failed: {e}')

        else:
            player = booking.player
            if not player:
                print(f'  no player for booking {booking.id}, skip')
                booking.rate_notified = True
                booking.save(update_fields=['rate_notified'])
                continue

            if Review.objects.filter(booking=booking, player=player).exists():
                print(f'  player {player} already rated, skip')
            else:
                try:
                    NotificationService.send_notification(
                        user=player,
                        title='قيّم الملعب',
                        body=f'كيف كانت تجربتك في {pitch_name}؟ قيّم الملعب الآن!',
                        notification_type='rate_pitch',
                        helper_id=booking.id,
                    )
                    print(f'  player {player} notified ✅')
                except Exception as e:
                    print(f'  player notification failed: {e}')

        booking.rate_notified = True
        booking.save(update_fields=['rate_notified'])


def notify_players_to_submit_score():
    """
    Runs every 5 minutes.
    Finds challenge bookings that have ended and notifies all players to submit their score.
    """
    now      = timezone.localtime(timezone.now())
    today    = now.date()
    now_time = now.time()
    yesterday = today - timedelta(days=1)

    challenges = Challenge.objects.filter(
        score_finalized=False,
        score_notified=False,
        status=ChallengeStatus.ACCEPTED,
        booking__status=BookingStatus.COMPLETED,
    ).filter(
        models.Q(date=today, end_time__lte=now_time) |
        models.Q(date=yesterday, end_time__gte='23:50')
    ).select_related('booking', 'pitch')

    print(f'[score_notify] found {challenges.count()} challenges')

    for challenge in challenges:
        pitch_name = challenge.pitch.name if hasattr(challenge.pitch, 'name') else 'الملعب'

        players = ChallengePlayerBooking.objects.filter(
            challenge=challenge
        ).select_related('player')

        print(f'  challenge {challenge.id} → {players.count()} players')

        for cp in players:
            player = cp.player
            try:
                NotificationService.send_notification(
                    user=player,
                    title='أضف نتيجة المباراة',
                    body=f'انتهت مباراتك في {pitch_name}، أضف النتيجة الآن!',
                    notification_type='submit_score',
                    helper_id=challenge.id,
                )
                print(f'    player {player} notified ✅')
            except Exception as e:
                print(f'    player {player} notification failed: {e}')

        challenge.score_notified = True
        challenge.save(update_fields=['score_notified'])


def remind_player_to_pay():
    """
    Runs every 5 minutes.
    Finds bookings with PAY status where PAYMENT_REMINDER_MINUTES have passed.
    Notifies the player AND all club workers.
    """
    # reminder_minutes = getattr(settings, 'PAYMENT_REMINDER_MINUTES', 30)
    # reminder_time    = timezone.now() - timedelta(minutes=reminder_minutes)

    bookings = list(Booking.objects.filter(
        status=BookingStatus.PAY,
        # created_at__lte=reminder_time,
        # pay_reminded=False,
    ).select_related('player', 'pitch', 'club'))

    # print(f'[pay_reminder] found {bookings.count()} bookings')

    for booking in bookings:
        player     = booking.player
        pitch_name = booking.pitch.name if hasattr(booking.pitch, 'name') else 'الملعب'

        # ── Notify player ──────────────────────────────────────────

        if booking.is_challenge:
            players = list(ChallengePlayerBooking.objects.only('player').filter(booking_id=booking.id).distinct())
            for cp in players:
                NotificationService.send_notification(
                    user=cp.player,
                    title='تذكير بالدفع',
                    body=f'لديك حجز غير مدفوع في {pitch_name} بتاريخ {booking.date}، يرجى إتمام الدفع.',
                    notification_type='payment_reminder',
                    helper_id=booking.id,
                 )
            
        else:
            if player:
                NotificationService.send_notification(
                    user=player,
                    title='تذكير بالدفع',
                    body=f'لديك حجز غير مدفوع في {pitch_name} بتاريخ {booking.date}، يرجى إتمام الدفع.',
                    notification_type='payment_reminder',
                    helper_id=booking.id,
                )
        

        # booking.pay_reminded = True
        booking.save(update_fields=['pay_reminded'])


def expire_pending_bookings():
    """
    Runs every 5 minutes.
    Finds bookings still pending after BOOKING_EXPIRY_HOURS and marks them expired.
    Notifies the player AND all club workers.
    """
    expiry_hours = getattr(settings, 'BOOKING_EXPIRY_HOURS', 2)
    expiry_time  = timezone.now() - timedelta(hours=expiry_hours)

    bookings = Booking.objects.filter(
        status__in=[
            BookingStatus.PAY,
        ],
        created_at__lte=expiry_time,
    ).select_related('club__manager', 'player', 'pitch')

    print(f'[expire_bookings] found {bookings.count()} bookings to expire')

    for booking in bookings:
        player     = booking.player
        pitch_name = booking.pitch.name

        booking.status = BookingStatus.EXPIRED
        booking.save(update_fields=['status'])
        print(f'  expired booking: {booking.id}')

        # ── Notify all club workers (manager + staff) ──────────────
        _notify_club_workers(
            club=booking.club,
            title='انتهت صلاحية الحجز',
            body=f'انتهت صلاحية الحجز في {pitch_name} بتاريخ {booking.date}',
            notification_type='booking_expired',
            helper_id=booking.id,
        )

        # ── Notify player ──────────────────────────────────────────
        if booking.is_challenge:
            Challenge.objects.filter(booking_id=booking.id).update(status=ChallengeStatus.EXPIRED)
            players = list(ChallengePlayerBooking.objects.only('player').filter(booking_id=booking.id).distinct())

            User.objects.filter(id__in=players).update(expired_time=F('expired_time') + 1)
            for cp in players:
                NotificationService.send_notification(
                    user=cp.player,
                    title='انتهت صلاحية حجزك',
                    body=f'انتهت صلاحية حجزك في {pitch_name} بتاريخ {booking.date}، يرجى الحجز مجدداً.',
                    notification_type='booking_expired',
                    helper_id=booking.id,
                )
                print(f'  player notified ✅')

        else:
            if player:
                    NotificationService.send_notification(
                        user=player,
                        title='انتهت صلاحية حجزك',
                        body=f'انتهت صلاحية حجزك في {pitch_name} بتاريخ {booking.date}، يرجى الحجز مجدداً.',
                        notification_type='booking_expired',
                        helper_id=booking.id,
                    )
                    User.objects.filter(id=booking.player_id).update(
                        disputed_time=F('disputed_time') + 1)
                    print(f'  player notified ✅')


def reject_pending_manager_bookings():


    now = timezone.now()

    expired_booking_qs = (
        Booking.objects
        .filter(status=BookingStatus.PENDING_MANAGER)
        .annotate(
            booking_end=ExpressionWrapper(
                F('date') + F('end_time'),
                output_field=DateTimeField()
            )
        )
        .filter(
            booking_end__lte=now
        )
    )

    # update bookings
    updated_bookings = expired_booking_qs.update(
        status=BookingStatus.REJECT
    )

    # expire related challenges
    updated_challenges = Challenge.objects.filter(
        booking_id__in=expired_booking_qs.values_list('id', flat=True)
    ).update(
        status=ChallengeStatus.REJECTED
    )

    print(
        f'[reject_pending_manager] '
        f'bookings={updated_bookings}, '
        f'challenges={updated_challenges}'
    )


def reject_expired_booking_notifications():
    
    expire_time = getattr(settings, 'BOOKING_NOTIFICATIONS_EXPIRY_HOURS', 2)
    expiry_time = timezone.now() - timedelta(hours=expire_time)

    updated = (
        BookingNotification.objects
        .filter(
            status=1,  # Pending
            created_at__lte=expiry_time
        )
        .update(
            status=3  # Reject
        )
    )

    print(f'[reject_booking_notifications] updated {updated} notifications')



def reject_expired_pending_team_challenges():


    now = timezone.now()

    updated = (
        Challenge.objects
        .filter(
            booking__isnull=True,
            status=ChallengeStatus.PENDING_TEAM,
        )
        .annotate(
            challenge_end=ExpressionWrapper(
                F('date') + F('end_time'),
                output_field=DateTimeField()
            )
        )
        .filter(
            challenge_end__lte=now
        )
        .update(
            status=ChallengeStatus.REJECTED
        )
    )

    print(f'[reject_pending_team] updated {updated} challenges')