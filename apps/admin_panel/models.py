from django.db import models
from django.utils import timezone
from apps.users.models import User


class Signalement(models.Model):
    """Signalements soumis par les utilisateurs (modération)"""

    TYPE_CHOICES = (
        ('rendez_vous', 'Non-respect du rendez-vous'),
        ('comportement', 'Comportement inapproprié'),
        ('fraude', 'Tentative de fraude'),
        ('autre', 'Autre'),
    )

    STATUS_CHOICES = (
        ('en_attente', 'En attente'),
        ('traite', 'Traité'),
        ('rejete', 'Rejeté'),
    )

    # Qui est signalé (nom affiché — l'utilisateur réel peut être lié ou supprimé)
    contenu = models.CharField(
        max_length=255,
        verbose_name="Sujet / Utilisateur signalé",
    )
    # Qui a signalé
    signale_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='signalements_emis',
        verbose_name="Signalé par",
    )
    signale_par_nom = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Nom signalant (cache)",
    )
    # Utilisateur visé (optionnel)
    utilisateur_vise = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='signalements_recus',
        verbose_name="Utilisateur visé",
    )

    raison = models.TextField(verbose_name="Raison du signalement")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='autre')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='en_attente')
    nombre_fois_signale = models.IntegerField(default=1)

    # Traitement
    note_admin = models.TextField(blank=True, verbose_name="Note de l'administrateur")
    traite_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='signalements_traites',
        verbose_name="Traité par",
    )
    traite_le = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'signalements'
        verbose_name = 'Signalement'
        verbose_name_plural = 'Signalements'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'type']),
            models.Index(fields=['utilisateur_vise']),
        ]

    def __str__(self):
        return f"Signalement #{self.id} — {self.contenu} ({self.get_status_display()})"


class Notification(models.Model):
    """Notifications envoyées aux administrateurs"""

    TYPE_CHOICES = (
        ('moderation', 'Modération'),
        ('utilisateurs', 'Utilisateurs'),
        ('statistique', 'Statistique'),
        ('vente', 'Vente'),
        ('vehicule', 'Véhicule'),
    )

    destinataire = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='admin_notifications',
        verbose_name="Destinataire",
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='moderation')
    titre = models.CharField(max_length=255)
    message = models.TextField()
    lu = models.BooleanField(default=False)
    lu_le = models.DateTimeField(null=True, blank=True)

    # Lien optionnel vers l'objet source
    lien_type = models.CharField(max_length=50, blank=True)  # ex: 'signalement', 'user'
    lien_id = models.CharField(max_length=50, blank=True)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'admin_notifications'
        verbose_name = 'Notification admin'
        verbose_name_plural = 'Notifications admin'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['destinataire', 'lu']),
            models.Index(fields=['type']),
        ]

    def __str__(self):
        return f"[{self.get_type_display()}] {self.titre} → {self.destinataire.username}"