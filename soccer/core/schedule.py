# core/schedule.py

from django_q.models import Schedule


def register_schedules():
    Schedule.objects.get_or_create(
        name='remind_owner_before_booking',
        defaults={
            'func': 'dashboard_booking.tasks.remind_owner_before_booking',
            'schedule_type': Schedule.MINUTES,
            'minutes': 5,
        }
    )
    
    Schedule.objects.get_or_create(
        name='expire_pending_bookings',
        defaults={
            'func': 'dashboard_booking.tasks.expire_pending_bookings',
            'schedule_type': Schedule.MINUTES,
            'minutes': 5,
        }
    )
    
    Schedule.objects.get_or_create(
        name='notify_players_to_submit_score',
        defaults={
            'func': 'dashboard_booking.tasks.notify_players_to_submit_score',
            'schedule_type': Schedule.MINUTES,
            'minutes': 5,
        }
    )

    Schedule.objects.get_or_create(
        name='remind_player_to_pay',
        defaults={
            'func': 'dashboard_booking.tasks.remind_player_to_pay',
            'schedule_type': Schedule.MINUTES,
            'minutes': 5,
        }
        
    )
    
    Schedule.objects.get_or_create(
        name='notify_players_to_rate',
        defaults={
            'func': 'dashboard_booking.tasks.notify_players_to_rate',
            'schedule_type': Schedule.MINUTES,
            'minutes': 5,
        }
    )