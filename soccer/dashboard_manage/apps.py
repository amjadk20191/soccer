from django.apps import AppConfig


class DashboardManageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard_manage'
    
    def ready(self):
        import dashboard_manage.signals.signals_rating 