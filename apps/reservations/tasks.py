from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from datetime import timedelta

from apps.reservations.models import Reservation, WorkProgress


@shared_task
def send_reservation_reminders():
    """Rappels quotidiens"""
    tomorrow = timezone.now() + timedelta(days=1)
    tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = tomorrow.replace(hour=23, minute=59, second=59)
    
    reservations = Reservation.objects.filter(
        date__range=(tomorrow_start, tomorrow_end),
        status__in=['confirmed', 'technician_dispatched']
    ).select_related('client__user', 'technician__user')
    
    for reservation in reservations:
        send_client_reminder_email.delay(reservation.id)
        if reservation.technician:
            send_technician_reminder_sms.delay(reservation.id)


@shared_task
def send_client_reminder_email(reservation_id):
    """Email de rappel au client"""
    try:
        reservation = Reservation.objects.get(id=reservation_id)
        
        subject = f"Rappel : Intervention prévue demain à {reservation.date.strftime('%H:%M')}"
        message = f"""
        Bonjour {reservation.client.user.get_full_name()},

        Ceci est un rappel pour votre intervention programmée demain:
        
        Date: {reservation.date.strftime('%d/%m/%Y à %H:%M')}
        Service: {reservation.get_service_type_display()}
        Technicien: {reservation.technician.user.get_full_name() if reservation.technician else 'À confirmer'}
        
        Merci de votre confiance.
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email='noreply@willy-mechanics.com',
            recipient_list=[reservation.client.user.email],
            fail_silently=False,
        )
        
        return f"Reminder sent to {reservation.client.user.email}"
    
    except Reservation.DoesNotExist:
        return f"Reservation {reservation_id} not found"


@shared_task
def send_technician_reminder_sms(reservation_id):
    """SMS de rappel au technicien"""
    try:
        reservation = Reservation.objects.get(id=reservation_id)
        
        if not reservation.technician:
            return "No technician assigned"
        
        message = f"""
        Rappel MecaPro:
        Intervention demain {reservation.date.strftime('%d/%m à %H:%M')}
        Client: {reservation.client.user.get_full_name()}
        """
        
        return f"SMS sent to {reservation.technician.user.telephone}"
    
    except Reservation.DoesNotExist:
        return f"Reservation {reservation_id} not found"


@shared_task
def send_arrival_notification(reservation_id):
    """Notification d'arrivée"""
    try:
        reservation = Reservation.objects.get(id=reservation_id)
        return f"Arrival notification sent for {reservation_id}"
    except Reservation.DoesNotExist:
        return f"Reservation {reservation_id} not found"


@shared_task
def send_diagnosis_notification(reservation_id):
    """Notification diagnostic prêt"""
    try:
        reservation = Reservation.objects.get(id=reservation_id)
        
        subject = "Diagnostic disponible"
        message = f"""
        Bonjour {reservation.client.user.get_full_name()},
        
        Le diagnostic de votre véhicule est maintenant disponible.
        Connectez-vous pour le consulter.
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email='noreply@willy-mechanics.com',
            recipient_list=[reservation.client.user.email],
            fail_silently=False,
        )
        
        return f"Diagnosis notification sent for {reservation_id}"
    
    except Reservation.DoesNotExist:
        return f"Reservation {reservation_id} not found"


@shared_task
def send_work_progress_notification(reservation_id, progress_id):
    """Notification de progression"""
    try:
        reservation = Reservation.objects.get(id=reservation_id)
        progress = WorkProgress.objects.get(id=progress_id)
        
        progress.client_notified = True
        progress.save()
        
        return f"Progress notification sent for {reservation_id}"
    
    except (Reservation.DoesNotExist, WorkProgress.DoesNotExist):
        return "Not found"


@shared_task
def send_completion_notification(reservation_id):
    """Notification de complétion"""
    try:
        reservation = Reservation.objects.get(id=reservation_id)
        
        subject = "Votre véhicule est prêt ! 🎉"
        message = f"""
        Bonjour {reservation.client.user.get_full_name()},
        
        Bonne nouvelle ! Votre véhicule est prêt.
        Vous pouvez venir le récupérer.
        
        Prix total: {reservation.price} FCFA
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email='noreply@willy-mechanics.com',
            recipient_list=[reservation.client.user.email],
            fail_silently=False,
        )
        
        return f"Completion notification sent for {reservation_id}"
    
    except Reservation.DoesNotExist:
        return f"Reservation {reservation_id} not found"


@shared_task
def send_evaluation_request(reservation_id):
    """Demande d'évaluation"""
    try:
        reservation = Reservation.objects.get(id=reservation_id)
        
        if hasattr(reservation, 'evaluation'):
            return "Already evaluated"
        
        subject = "Comment s'est passée votre intervention ?"
        message = f"""
        Bonjour {reservation.client.user.get_full_name()},
        
        Nous espérons que l'intervention s'est bien passée.
        Pouvez-vous prendre quelques instants pour l'évaluer?
        
        Votre avis nous aide à améliorer nos services.
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email='noreply@willy-mechanics.com',
            recipient_list=[reservation.client.user.email],
            fail_silently=False,
        )
        
        return f"Evaluation request sent for {reservation_id}"
    
    except Reservation.DoesNotExist:
        return f"Reservation {reservation_id} not found"