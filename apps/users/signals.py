from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.users.models import User, Client, Technician, Vendor, Administrator


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