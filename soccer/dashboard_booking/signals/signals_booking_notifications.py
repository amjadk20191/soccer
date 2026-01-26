from rest_framework.exceptions import ValidationError # <--- Use this one
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import Notification
from dashboard_booking.models import BookingNotification
from core.models import User
from dashboard_manage.models import Club


@receiver(post_save, sender=BookingNotification, dispatch_uid="booking_notification_created_signal")
def booking_notification_created(sender, instance, created, **kwargs):
    if created:
        # This code runs ONLY when a new row is created
        try:
            club = Club.objects.filter(id=instance.send_by_id).values("name", "manager_id").first()
            if not club:
                raise ValidationError({"detail": "Associated club not found."})
            
            notification_message = (
            f"نادي: {club['name']}\n"
            f"يقترح تعديل وقت الحجز من \n"
            f"{instance.old_date} ({instance.old_start_time} - {instance.old_end_time})\n"
            f"الى\n"
            f"{instance.new_date} ({instance.new_start_time} - {instance.new_end_time})"
            )

            Notification.objects.create(
               user_id = instance.send_to_id,     
                sender_id = club["manager_id"],        
               notification_type = 'Booking Notification',
               title = 'اقتراح لتعديل الوقت',
               message = notification_message
            )

        except Exception as e:
            raise ValidationError({"detail": f"Error creating notification a : {str(e)}"})
   
    else:
        return
    
