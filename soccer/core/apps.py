from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(_register_schedules_after_migrate, sender=self)

            
def _register_schedules_after_migrate(sender, **kwargs):
    from core.schedule import register_schedules
    register_schedules()