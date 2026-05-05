from django.apps import AppConfig


class PlayerCompetitionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'player_competition'
    def ready(self):
        import player_competition.signals.signals_challenge_result
