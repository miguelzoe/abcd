from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from apps.marketplace.models import Commande, Avis


@receiver(post_save, sender=Commande)
def send_commande_notification(sender, instance, created, **kwargs):
    """
    Envoyer une notification lors de la création ou modification d'une commande
    (À implémenter avec Celery pour l'envoi d'emails/SMS)
    """
    if created:
        # TODO: Envoyer notification au client
        # send_order_confirmation.delay(instance.id)
        pass
    else:
        # TODO: Envoyer notification selon le changement de statut
        # if instance.status == 'shipped':
        #     send_shipping_notification.delay(instance.id)
        # elif instance.status == 'delivered':
        #     send_delivery_confirmation.delay(instance.id)
        pass


@receiver(post_save, sender=Avis)
def update_product_rating_on_review(sender, instance, created, **kwargs):
    """
    Mettre à jour le rating du produit quand un avis est créé
    (Optionnel si on utilise une agrégation dynamique)
    """
    if created:
        # TODO: Recalculer et cacher le rating du produit si nécessaire
        pass


@receiver(pre_save, sender=Commande)
def set_dates_on_status_change(sender, instance, **kwargs):
    """
    Mettre à jour automatiquement les dates selon le statut
    """
    if instance.pk:
        try:
            old_instance = Commande.objects.get(pk=instance.pk)
            
            # Si le statut change vers 'shipped'
            if old_instance.status != 'shipped' and instance.status == 'shipped':
                if not instance.date_expedition:
                    from django.utils import timezone
                    instance.date_expedition = timezone.now()
            
            # Si le statut change vers 'delivered'
            if old_instance.status != 'delivered' and instance.status == 'delivered':
                if not instance.date_livraison:
                    from django.utils import timezone
                    instance.date_livraison = timezone.now()
        
        except Commande.DoesNotExist:
            pass