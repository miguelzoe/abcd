from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from apps.reservations.models import Reservation, Evaluation


@receiver(post_save, sender=Evaluation)
def update_technician_rating_on_evaluation(sender, instance, created, **kwargs):
    """Recalculer le rating"""
    if created:
        from apps.reservations.services import update_technician_rating
        update_technician_rating(instance.technician)


@receiver(pre_save, sender=Reservation)
def update_technician_status_on_reservation_change(sender, instance, **kwargs):
    """Mettre à jour le statut du technicien"""
    if instance.pk:
        try:
            old_instance = Reservation.objects.get(pk=instance.pk)
            
            if old_instance.status in ['confirmed', 'in_progress'] and \
               instance.status in ['cancelled', 'completed']:
                if instance.technician and instance.technician.status == 'busy':
                    instance.technician.status = 'available'
                    instance.technician.save()
            
            elif old_instance.status in ['pending', 'cancelled'] and \
                 instance.status in ['confirmed', 'in_progress']:
                if instance.technician and instance.technician.status == 'available':
                    instance.technician.status = 'busy'
                    instance.technician.save()
        
        except Reservation.DoesNotExist:
            pass


@receiver(post_save, sender=Reservation)
def send_reservation_notification(sender, instance, created, **kwargs):
    """Envoyer une notification"""
    if created:
        pass
    else:
        pass
