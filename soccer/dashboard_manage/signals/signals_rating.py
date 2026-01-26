from rest_framework.exceptions import ValidationError # <--- Use this one
from django.db.models.signals import post_save
from django.dispatch import receiver
from dashboard_manage.models import Club
from player_booking.models import Review

@receiver(post_save, sender=Review, dispatch_uid="review_created_signal")
def review_created(sender, instance, created, **kwargs):
    if created:
        # This code runs ONLY when a new row is created
        try:
            
            club = Club.objects.select_for_update().only("rating_avg", "rating_count").get(id=instance.club_id)

            new_count = club.rating_count + 1
            new_avg = ((club.rating_avg * club.rating_count) + instance.rating) / new_count

            club.rating_count = new_count
            club.rating_avg = round(new_avg, 2)
            club.save(update_fields=["rating_count", "rating_avg"])

        except Club.DoesNotExist:
            raise ValidationError({"detail": "Associated club not found."})
        except Exception as e:
            raise ValidationError({"detail": f"Error updating club rating: {str(e)}"})
    else:
        return
