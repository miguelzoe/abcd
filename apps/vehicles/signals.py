from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from apps.vehicles.models import Vehicle, MaintenanceRecord


@receiver(post_save, sender=MaintenanceRecord)
def update_vehicle_kilometrage_on_maintenance(sender, instance, created, **kwargs):
    """
    Mettre à jour automatiquement le kilométrage du véhicule 
    quand une maintenance est créée
    """
    if created:
        vehicle = instance.vehicle
        if instance.kilometrage_actuel > vehicle.kilometrage:
            vehicle.kilometrage = instance.kilometrage_actuel
            vehicle.save()


@receiver(pre_save, sender=Vehicle)
def update_vehicle_status_based_on_maintenance(sender, instance, **kwargs):
    """
    Logique pour changer le statut du véhicule automatiquement
    (À personnaliser selon les besoins métier)
    """
    pass


@receiver(post_save, sender=MaintenanceRecord)
def send_maintenance_notification(sender, instance, created, **kwargs):
    """
    Envoyer une notification lors de la création d'une maintenance
    (À implémenter avec Celery pour l'envoi d'emails/SMS)
    """
    if created:
        # TODO: Envoyer notification aux propriétaires du véhicule
        # send_maintenance_created_notification.delay(instance.id)
        pass