from django.db.models.signals import pre_save
from django.dispatch import receiver

from ..models import Club, ClubOpeningTimeHistory


@receiver(pre_save, sender=Club)
def log_opening_time_change(sender, instance, **kwargs):


    previous = Club.objects.only("open_time", "close_time").filter(pk=instance.pk).first()


    if previous and (previous.open_time == instance.open_time and previous.close_time == instance.close_time):
        return
    
    ClubOpeningTimeHistory.objects.create(
        club_id    = instance.pk,
        open_time  = instance.open_time,
        close_time = instance.close_time,
    )