
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from player_booking.models import Booking, BookingStatus, Review
from core.services.notification_service import NotificationService
from player_competition.models import ChallengePlayerBooking, Challenge, ChallengeStatus
from django.db import models

def remind_owner_before_booking():
    now = timezone.localtime(timezone.now())
    today = now.date()

    time_start = (now + timedelta(minutes=5)).time()
    time_end   = (now + timedelta(minutes=40)).time()

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
        owner       = booking.club.manager if booking.club else None
        player      = booking.player
        pitch_name  = booking.pitch.name if hasattr(booking.pitch, 'name') else 'الملعب'
        start_str   = booking.start_time.strftime('%H:%M')
        player_name = player.full_name if player else 'لاعب'

        

        # ── Notify owner ──────────────────────────────
        if owner:
            try:
                NotificationService.send_notification(
                    user=owner,
                    title='تذكير بحجز قادم',
                    body=f'لديك حجز في {pitch_name} الساعة {start_str} من {player_name}',
                    notification_type='booking_reminder',
                    helper_id=booking.id,

                )
                
            except Exception as e:
                print(f'  owner notification failed: {e}')
        
            

        # ── Notify player ─────────────────────────────
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
        

        # always mark reminded even if notification failed
        booking.owner_reminded = True
        booking.save(update_fields=['owner_reminded'])
        
def notify_players_to_rate():
    """
    Runs every 5 minutes.
    Finds completed bookings where end_time has passed.
    Regular booking → notify the player who booked.
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
            # notify all players who played
            challenge_players = ChallengePlayerBooking.objects.filter(
                booking=booking
            ).select_related('player')

            print(f'  challenge booking {booking.id} → {challenge_players.count()} players')

            for cp in challenge_players:
                player = cp.player
                already_rated = Review.objects.filter(
                    booking=booking,
                    player=player
                ).exists()

                if already_rated:
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
            # notify only the player who booked
            player = booking.player

            if not player:
                print(f'  no player for booking {booking.id}, skip')
                booking.rate_notified = True
                booking.save(update_fields=['rate_notified'])
                continue

            already_rated = Review.objects.filter(
                booking=booking,
                player=player
            ).exists()

            if already_rated:
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
    Finds challenge bookings that have ended
    and notifies all players to submit their score.
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
    Finds bookings with PENDING_PAY status where 
    PAYMENT_REMINDER_MINUTES have passed since creation.
    Sends a reminder to the player to complete payment.
    """
    reminder_minutes = getattr(settings, 'PAYMENT_REMINDER_MINUTES', 30)
    reminder_time    = timezone.now() - timedelta(minutes=reminder_minutes)

    bookings = Booking.objects.filter(
        status=BookingStatus.PAY,
        created_at__lte=reminder_time,
        pay_reminded=False,
    ).select_related('player', 'pitch', 'club')

    print(f'[pay_reminder] found {bookings.count()} bookings')

    for booking in bookings:
        player     = booking.player
        pitch_name = booking.pitch.name if hasattr(booking.pitch, 'name') else 'الملعب'

        if player:
            try:
                NotificationService.send_notification(
                    user=player,
                    title='تذكير بالدفع',
                    body=f'لديك حجز غير مدفوع في {pitch_name} بتاريخ {booking.date}، يرجى إتمام الدفع.',
                    notification_type='payment_reminder',
                    helper_id=booking.id,
                )
                print(f'  player {player} notified ✅')
            except Exception as e:
                print(f'  player notification failed: {e}')

        booking.pay_reminded = True
        booking.save(update_fields=['pay_reminded'])


def expire_pending_bookings():
    """
    Runs every 5 minutes.
    Finds bookings that are still pending after BOOKING_EXPIRY_HOURS
    and marks them as expired.
    """
    expiry_hours = getattr(settings, 'BOOKING_EXPIRY_HOURS', 2)
    expiry_time  = timezone.now() - timedelta(hours=expiry_hours)

    bookings = Booking.objects.filter(
        status__in=[
            BookingStatus.PAY,
            BookingStatus.PENDING_PLAYER,
        ],
        created_at__lte=expiry_time,
    ).select_related('club__manager', 'player', 'pitch')

    print(f'[expire_bookings] found {bookings.count()} bookings to expire')

    for booking in bookings:
        owner  = booking.club.manager if booking.club else None
        player = booking.player

        # change status to expired
        booking.status = BookingStatus.EXPIRED
        booking.save(update_fields=['status'])

        print(f'  expired booking: {booking.id}')

        # notify owner
        if owner:
            try:
                NotificationService.send_notification(
                    user=owner,
                    title='انتهت صلاحية الحجز',
                    body=f'انتهت صلاحية الحجز في {booking.pitch.name} بتاريخ {booking.date}',
                    notification_type='booking_expired',
                    helper_id=booking.id,

                )
                print(f'  owner notified ✅')
            except Exception as e:
                print(f'  owner notification failed: {e}')

        # notify player
        if player:
            try:
                NotificationService.send_notification(
                    user=player,
                    title='انتهت صلاحية حجزك',
                    body=f'انتهت صلاحية حجزك في {booking.pitch.name} بتاريخ {booking.date}، يرجى الحجز مجدداً.',
                    notification_type='booking_expired',
                    helper_id=booking.id,

                )
                print(f'  player notified ✅')
            except Exception as e:
                print(f'  player notification failed: {e}')
