from django.apps import AppConfig


class VehiclesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.vehicles'
    verbose_name = 'Gestion des Véhicules'
    
    def ready(self):
        """Importer les signaux au démarrage"""
        import apps.vehicles.signals