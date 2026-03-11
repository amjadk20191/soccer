from django.apps import AppConfig


class DashboardManageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard_manage'
    
    def ready(self):
        import dashboard_manage.signals.signals_rating 
        import dashboard_manage.signals.signals_booking_statistics 
        import dashboard_manage.signals.signals_booking_equipment_statistics
        import dashboard_manage.signals.signals_booking_equipment_statistics_fromBooking
        import dashboard_manage.signals.signals_log_opening_time_change