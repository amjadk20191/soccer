from rest_framework.exceptions import ValidationError # <--- Use this one
from django.db.models.signals import post_save
from django.dispatch import receiver
from player_booking.models import Booking
from dashboard_booking.models import BookingStatusHistory


@receiver(post_save, sender=Booking, dispatch_uid="bookin_status_history_update_signal")
def bookin_status_history_created(sender, instance, created, **kwargs):
    update_fields = kwargs.get("update_fields")
    print(update_fields)
    if created or (update_fields and "status" in list(update_fields)):

        try:

            BookingStatusHistory.objects.create(
                                                booking_id = instance.pk,
                                                status = instance.status,
                                                date = instance.date,
                                                start_time = instance.start_time,
                                                end_time = instance.end_time
                                                )

        except Exception as e:
            raise ValidationError({"detail": f"Error creating BookingStatusHistory a : {str(e)}"})


    
