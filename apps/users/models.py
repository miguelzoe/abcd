from django.db import models
from django.contrib.auth.models import AbstractUser
from apps.users.managers import UserManager
from django.contrib.gis.db import models as gis_models
from django.utils import timezone


class User(AbstractUser):
    objects = UserManager()

    """Modèle utilisateur de base avec extension géographique"""
    USER_TYPES = (
        ('client', 'Client intervention'),
        ('technician', 'Technicien intervention'),
        ('marketplace_customer', 'Client marketplace'),
        ('vendor', 'Vendeur marketplace'),
        ('auto_shop', 'Boutique automobile'),
        ('administrator', 'Administrateur'),
    )

    user_type = models.CharField(max_length=30, choices=USER_TYPES)
    telephone = models.CharField(max_length=20, unique=True)
    address = models.CharField(max_length=255, blank=True, default='')
    location = gis_models.PointField(null=True, blank=True, srid=4326)
    is_available = models.BooleanField(default=True)
    # Photo de profil robuste pour Render: l'image est stockée en base
    # de données et servie via /api/users/<id>/profile_photo/.
    profile_photo = models.ImageField(upload_to='users/profile_photos/', null=True, blank=True)
    profile_photo_data = models.BinaryField(null=True, blank=True, editable=False)
    profile_photo_content_type = models.CharField(max_length=120, blank=True, default='')
    profile_photo_filename = models.CharField(max_length=255, blank=True, default='')

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    password_changed_at = models.DateTimeField(default=timezone.now)
    password_expiry_notified_at = models.DateTimeField(null=True, blank=True)

    REQUIRED_FIELDS = ['email', 'telephone']

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
    APPROVAL_STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('approved', 'Actif'),
        ('rejected', 'Refusé'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='technician_profile')
    certifications = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    specializations = models.JSONField(default=list, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_interventions = models.IntegerField(default=0)
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True, default='')
    years_experience = models.PositiveSmallIntegerField(default=0)
    profile_photo = models.ImageField(upload_to='technicians/profile_photos/', null=True, blank=True)

    class Meta:
        db_table = 'technicians'
        verbose_name = 'Technicien'
        verbose_name_plural = 'Techniciens'
        indexes = [
            models.Index(fields=['status', 'rating']),
            models.Index(fields=['approval_status']),
        ]

    def __str__(self):
        return f"Technicien: {self.user.get_full_name() or self.user.username}"


class TechnicianDocument(models.Model):
    """
    Documents justificatifs des techniciens.

    Les nouveaux documents sont stockés directement en base de données
    dans ``file_data`` afin d'éviter toute dépendance à Render Disk ou au
    filesystem éphémère de Render. Le champ ``file`` est conservé uniquement
    pour compatibilité avec les anciennes lignes déjà créées en /media/.
    """
    VALIDATION_STATUS_CHOICES = (
        ('non_verifie', 'Non vérifié'),
        ('valide', 'Valide'),
        ('invalide', 'Invalide'),
    )

    DOCUMENT_TYPE_CHOICES = (
        ('piece_identite', "CNI ou pièce d’identité"),
        ('certificat', 'Certificat professionnel'),
        ('experience', "Justificatif d’expérience"),
        ('assurance', 'Assurance'),
        ('autre', 'Autre document'),
    )

    technician = models.ForeignKey(
        Technician,
        on_delete=models.CASCADE,
        related_name='documents'
    )

    # Ancien stockage fichier conservé pour compatibilité.
    file = models.FileField(upload_to='technicians/documents/', null=True, blank=True)

    # Nouveau stockage durable en base de données.
    file_data = models.BinaryField(null=True, blank=True, editable=False)
    original_filename = models.CharField(max_length=255, blank=True, default='')
    content_type = models.CharField(max_length=120, blank=True, default='application/octet-stream')
    file_size = models.PositiveIntegerField(default=0)
    document_type = models.CharField(max_length=40, choices=DOCUMENT_TYPE_CHOICES, default='autre')

    name = models.CharField(max_length=255, blank=True, default='')
    validation_status = models.CharField(max_length=20, choices=VALIDATION_STATUS_CHOICES, default='non_verifie')
    validation_comment = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'technician_documents'
        verbose_name = 'Document technicien'
        verbose_name_plural = 'Documents techniciens'
        indexes = [
            models.Index(fields=['technician', 'validation_status']),
            models.Index(fields=['document_type']),
        ]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return self.name or self.original_filename or (self.file.name if self.file else '') or f'Document #{self.pk}'

    @property
    def has_database_file(self):
        return self.file_data is not None and len(self.file_data or b'') > 0

    @property
    def safe_content_type(self):
        if self.content_type:
            return self.content_type
        filename = self.display_name.lower()
        if filename.endswith('.pdf'):
            return 'application/pdf'
        if filename.endswith('.png'):
            return 'image/png'
        if filename.endswith('.webp'):
            return 'image/webp'
        if filename.endswith('.jpg') or filename.endswith('.jpeg'):
            return 'image/jpeg'
        return 'application/octet-stream'


class Vendor(models.Model):
    """Profil partenaire marketplace validé par l'administration."""
    PARTNER_TYPES = (
        ('parts_seller', 'Vendeur de pièces / produits'),
        ('auto_shop', 'Boutique automobile / location'),
    )
    APPROVAL_STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('approved', 'Approuvé'),
        ('rejected', 'Refusé'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor_profile')
    company_name = models.CharField(max_length=200, blank=True, default='', verbose_name="Nom de l'entreprise")
    business_license = models.CharField(max_length=100, blank=True, default='', verbose_name="Licence commerciale")
    partner_type = models.CharField(max_length=30, choices=PARTNER_TYPES, default='parts_seller')
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True, default='')
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_marketplace_partners',
    )
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_sales = models.IntegerField(default=0, verbose_name="Total des ventes")
    is_verified = models.BooleanField(default=False, verbose_name="Vérifié")

    class Meta:
        db_table = 'vendors'
        verbose_name = 'Partenaire marketplace'
        verbose_name_plural = 'Partenaires marketplace'

    def __str__(self):
        return f"Partenaire: {self.company_name or self.user.get_full_name()}"


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
