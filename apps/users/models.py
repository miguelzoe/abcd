from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.gis.db import models as gis_models
from django.utils import timezone


class User(AbstractUser):
    """Modèle utilisateur de base avec extension géographique"""
    USER_TYPES = (
        ('client', 'Client'),
        ('technician', 'Technicien'),
        ('vendor', 'Vendeur'),
        ('administrator', 'Administrateur'),
    )

    user_type = models.CharField(max_length=20, choices=USER_TYPES)
    telephone = models.CharField(max_length=20, unique=True)
    address = models.CharField(max_length=255, blank=True, default='')
    location = gis_models.PointField(null=True, blank=True, srid=4326)
    is_available = models.BooleanField(default=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
        indexes = [
            models.Index(fields=['user_type', 'is_available']),
            models.Index(fields=['telephone']),
        ]

    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"


class PushToken(models.Model):
    """Token Expo Push Notifications (un utilisateur peut avoir plusieurs appareils)."""
    PLATFORM_CHOICES = (
        ('ios', 'iOS'),
        ('android', 'Android'),
        ('web', 'Web'),
        ('unknown', 'Unknown'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_tokens')
    token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default='unknown')
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'push_tokens'
        verbose_name = 'Token push'
        verbose_name_plural = 'Tokens push'
        indexes = [
            models.Index(fields=['user', 'platform']),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.platform}"


class Notification(models.Model):
    """Notifications internes + push (si token disponible)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=140, default='')
    body = models.TextField(default='')
    data = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'notifications'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['user', 'read_at']),
        ]

    @property
    def is_read(self):
        return self.read_at is not None

    def mark_read(self):
        if not self.read_at:
            self.read_at = timezone.now()
            self.save(update_fields=['read_at'])


class Client(models.Model):
    """Profil Client - Utilisateur qui réserve des techniciens et achète des produits"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client_profile')
    historique_commandes = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'clients'
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'

    def __str__(self):
        return f"Client: {self.user.get_full_name() or self.user.username}"


class Technician(models.Model):
    """Profil Technicien - Prestataire de services techniques"""
    STATUS_CHOICES = (
        ('available', 'Disponible'),
        ('busy', 'Occupé'),
        ('offline', 'Hors ligne'),
    )

    SPECIALIZATION_CHOICES = [
        'Mécanique générale',
        'Électricité automobile',
        'Carrosserie & peinture',
        'Climatisation',
        'Pneumatiques & freins',
        'Moteur & transmission',
        'Diagnostic électronique',
        'Vitrage & pare-brise',
        'Géométrie & suspension',
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='technician_profile')
    certifications = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    specializations = models.JSONField(default=list, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_interventions = models.IntegerField(default=0)

    class Meta:
        db_table = 'technicians'
        verbose_name = 'Technicien'
        verbose_name_plural = 'Techniciens'
        indexes = [
            models.Index(fields=['status', 'rating']),
        ]

    def __str__(self):
        return f"Technicien: {self.user.get_full_name() or self.user.username}"


class TechnicianDocument(models.Model):
    """Documents uploadés par un technicien à l'inscription ou plus tard"""
    technician = models.ForeignKey(
        Technician,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    file = models.FileField(upload_to='technicians/documents/')
    name = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'technician_documents'
        verbose_name = 'Document technicien'
        verbose_name_plural = 'Documents techniciens'

    def __str__(self):
        return self.name or self.file.name


class Vendor(models.Model):
    """Profil Vendeur - Vendeur de produits sur la marketplace"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor_profile')
    company_name = models.CharField(max_length=200, blank=True, default='', verbose_name="Nom de l'entreprise")
    business_license = models.CharField(max_length=100, blank=True, default='', verbose_name="Licence commerciale")
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_sales = models.IntegerField(default=0, verbose_name="Total des ventes")
    is_verified = models.BooleanField(default=False, verbose_name="Vérifié")

    class Meta:
        db_table = 'vendors'
        verbose_name = 'Vendeur'
        verbose_name_plural = 'Vendeurs'

    def __str__(self):
        return f"Vendeur: {self.company_name or self.user.get_full_name()}"


class Administrator(models.Model):
    """Profil Administrateur - Gestion de la plateforme"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    permissions = models.JSONField(default=dict, blank=True)
    department = models.CharField(max_length=100, blank=True, default='', verbose_name="Département")

    class Meta:
        db_table = 'administrators'
        verbose_name = 'Administrateur'
        verbose_name_plural = 'Administrateurs'

    def __str__(self):
        return f"Admin: {self.user.get_full_name() or self.user.username}"
