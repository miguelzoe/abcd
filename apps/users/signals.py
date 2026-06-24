from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from apps.users.models import User, Client, Technician, Vendor, Administrator, Notification


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Créer automatiquement le profil correspondant au type d'utilisateur
    lors de la création d'un User
    """
    if created:
        if instance.user_type == 'client' and not hasattr(instance, 'client_profile'):
            Client.objects.create(user=instance)
        elif instance.user_type == 'technician' and not hasattr(instance, 'technician_profile'):
            Technician.objects.create(user=instance)
        elif instance.user_type == 'vendor' and not hasattr(instance, 'vendor_profile'):
            Vendor.objects.create(user=instance)
        elif instance.user_type == 'administrator' and not hasattr(instance, 'admin_profile'):
            Administrator.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Sauvegarder le profil lorsque le User est sauvegardé
    """
    if instance.user_type == 'client' and hasattr(instance, 'client_profile'):
        instance.client_profile.save()
    elif instance.user_type == 'technician' and hasattr(instance, 'technician_profile'):
        instance.technician_profile.save()
    elif instance.user_type == 'vendor' and hasattr(instance, 'vendor_profile'):
        instance.vendor_profile.save()
    elif instance.user_type == 'administrator' and hasattr(instance, 'admin_profile'):
        instance.admin_profile.save()


@receiver(post_save, sender=Technician)
def notify_technician_approval_status(sender, instance, created, **kwargs):
    """
    Notifier le technicien par email lorsque son statut d'approbation change
    """
    if not created and instance.approval_status in ['approved', 'rejected']:
        # Vérifier si le statut a changé
        if hasattr(instance, '_original_approval_status'):
            if instance._original_approval_status != instance.approval_status:
                subject = "Mise à jour de votre inscription Cartronic"
                if instance.approval_status == 'approved':
                    message = (
                        f"Bonjour {instance.user.get_full_name() or instance.user.username},\n\n"
                        "Félicitations ! Votre inscription en tant que technicien sur Cartronic a été approuvée.\n"
                        "Vous pouvez maintenant accéder à la plateforme mobile et commencer à recevoir des missions.\n\n"
                        "Cordialement,\n"
                        "L'équipe Cartronic"
                    )
                elif instance.approval_status == 'rejected':
                    reason = instance.rejection_reason or "Aucune raison spécifiée"
                    message = (
                        f"Bonjour {instance.user.get_full_name() or instance.user.username},\n\n"
                        "Nous regrettons de vous informer que votre inscription en tant que technicien sur Cartronic a été refusée.\n"
                        f"Raison : {reason}\n\n"
                        "Vous pouvez contacter notre support pour plus d'informations.\n\n"
                        "Cordialement,\n"
                        "L'équipe Cartronic"
                    )

                send_mail(
                    subject=subject,
                    message=message,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                    recipient_list=[instance.user.email],
                    fail_silently=True,
                )


def _track_technician_approval_status(sender, instance, **kwargs):
    """
    Tracker le statut d'approbation original pour détecter les changements
    """
    if hasattr(instance, 'approval_status'):
        instance._original_approval_status = getattr(instance, '_original_approval_status', instance.approval_status)


# Connecter le signal pre_save pour tracker les changements
from django.db.models.signals import pre_save
@receiver(pre_save, sender=Technician)
def track_technician_changes(sender, instance, **kwargs):
    _track_technician_approval_status(sender, instance, **kwargs)