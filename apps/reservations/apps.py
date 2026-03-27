from django.apps import AppConfig


class ReservationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.reservations'
    verbose_name = 'Gestion des Réservations'
    
    def ready(self):
        """Importer les signaux au démarrage"""
        import apps.reservations.signals