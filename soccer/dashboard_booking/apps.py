from django.apps import AppConfig


class DashboardBookingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard_booking'
    
    def ready(self):
        import dashboard_booking.signals.signals_booking_notifications
        import dashboard_booking.signals.signals_booking_status_history