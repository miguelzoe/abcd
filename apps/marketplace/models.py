from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import uuid

from apps.users.models import Client

User = get_user_model()


class Produit(models.Model):
    """Produits de la marketplace"""
    CATEGORY_CHOICES = (
        ('electronic', 'Électronique'),
        ('mechanic', 'Mécanique'),
        ('accessory', 'Accessoire'),
        ('tool', 'Outil'),
        ('part', 'Pièce détachée'),
        ('other', 'Autre'),
    )
    
    id = models.CharField(max_length=50, primary_key=True, editable=False)
    nom = models.CharField(max_length=200, verbose_name="Nom du produit")
    description = models.TextField(verbose_name="Description")
    prix = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Prix"
    )
    stock = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Stock disponible"
    )
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        verbose_name="Catégorie"
    )
    images = models.JSONField(default=list, blank=True, verbose_name="Images (URLs)")
    
    # Vendeur
    vendeur = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='produits',
        limit_choices_to={'user_type__in': ['vendor', 'auto_shop', 'administrator']},
        verbose_name="Vendeur"
    )
    
    # Informations techniques
    marque = models.CharField(max_length=100, blank=True, verbose_name="Marque")
    reference = models.CharField(max_length=100, blank=True, verbose_name="Référence")
    
    # Statut
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    is_featured = models.BooleanField(default=False, verbose_name="Produit vedette")
    
    # Métadonnées - CORRIGÉ avec default
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'produits'
        verbose_name = 'Produit'
        verbose_name_plural = 'Produits'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category', 'prix']),
            models.Index(fields=['vendeur']),
            models.Index(fields=['is_active', 'is_featured']),
            models.Index(fields=['nom']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f"PROD-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.nom} - {self.prix} FCFA"
    
    @property
    def is_in_stock(self):
        return self.stock > 0
    
    @property
    def total_sold(self):
        """Quantité totale vendue"""
        return self.lignecommande_set.aggregate(
            models.Sum('quantite')
        )['quantite__sum'] or 0


class Piece(models.Model):
    """Pièces détachées"""
    id = models.CharField(max_length=50, primary_key=True, editable=False)
    nom = models.CharField(max_length=200, verbose_name="Nom de la pièce")
    reference = models.CharField(max_length=100, unique=True, verbose_name="Référence")
    prix = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Prix"
    )
    stock = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Stock"
    )
    
    # Relation avec produit (optionnel)
    produit = models.ForeignKey(
        Produit,
        on_delete=models.CASCADE,
        related_name='pieces',
        null=True,
        blank=True,
        verbose_name="Produit associé"
    )
    
    # Informations
    description = models.TextField(blank=True, verbose_name="Description")
    compatibilite = models.JSONField(
        default=list,
        blank=True,
        help_text="Liste des véhicules compatibles",
        verbose_name="Compatibilité"
    )
    
    # Métadonnées - CORRIGÉ avec default
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'pieces'
        verbose_name = 'Pièce détachée'
        verbose_name_plural = 'Pièces détachées'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reference']),
            models.Index(fields=['produit']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f"PIECE-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.nom} - {self.reference}"


class Commande(models.Model):
    """Commandes marketplace"""
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('processing', 'En traitement'),
        ('shipped', 'Expédiée'),
        ('delivered', 'Livrée'),
        ('cancelled', 'Annulée'),
    )
    
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('paid', 'Payée'),
        ('failed', 'Échouée'),
        ('refunded', 'Remboursée'),
    )
    
    id = models.CharField(max_length=50, primary_key=True, editable=False)
    # CORRIGÉ avec default
    date = models.DateTimeField(default=timezone.now, verbose_name="Date de commande")
    
    # Client
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='commandes',
        verbose_name="Client"
    )
    
    # Statut
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Statut"
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending',
        verbose_name="Statut paiement"
    )
    
    # Prix
    prix_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Prix total"
    )
    frais_livraison = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Frais de livraison"
    )
    
    # Livraison - CORRIGÉ avec default et blank
    adresse_livraison = models.TextField(
        default='',
        blank=True,
        verbose_name="Adresse de livraison"
    )
    telephone_livraison = models.CharField(
        max_length=20,
        default='',
        blank=True,
        verbose_name="Téléphone livraison"
    )
    
    # Notes
    notes = models.TextField(blank=True, default='', verbose_name="Notes")
    notes_admin = models.TextField(blank=True, default='', verbose_name="Notes administrateur")
    
    # Dates
    date_paiement = models.DateTimeField(null=True, blank=True, verbose_name="Date de paiement")
    date_expedition = models.DateTimeField(null=True, blank=True, verbose_name="Date d'expédition")
    date_livraison = models.DateTimeField(null=True, blank=True, verbose_name="Date de livraison")
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'commandes'
        verbose_name = 'Commande'
        verbose_name_plural = 'Commandes'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['date']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f"CMD-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Commande {self.id} - {self.client.user.username}"
    
    @property
    def prix_total_avec_livraison(self):
        return self.prix_total + self.frais_livraison
    
    @property
    def nombre_articles(self):
        return self.lignes.aggregate(
            models.Sum('quantite')
        )['quantite__sum'] or 0


class LigneCommande(models.Model):
    """Lignes de commande"""
    commande = models.ForeignKey(
        Commande,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name="Commande"
    )
    produit = models.ForeignKey(
        Produit,
        on_delete=models.CASCADE,
        verbose_name="Produit"
    )
    quantite = models.IntegerField(
        validators=[MinValueValidator(1)],
        default=1,
        verbose_name="Quantité"
    )
    prix_unitaire = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Prix unitaire"
    )
    
    class Meta:
        db_table = 'lignes_commande'
        verbose_name = 'Ligne de commande'
        verbose_name_plural = 'Lignes de commande'
    
    def __str__(self):
        return f"{self.quantite}x {self.produit.nom}"
    
    @property
    def prix_total(self):
        return self.quantite * self.prix_unitaire


class Avis(models.Model):
    """Avis sur les produits"""
    produit = models.ForeignKey(
        Produit,
        on_delete=models.CASCADE,
        related_name='avis',
        verbose_name="Produit"
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='avis',
        verbose_name="Client"
    )
    note = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5,
        verbose_name="Note"
    )
    commentaire = models.TextField(default='', blank=True, verbose_name="Commentaire")
    
    # Achat vérifié
    commande = models.ForeignKey(
        Commande,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='avis',
        verbose_name="Commande"
    )
    
    # CORRIGÉ avec default
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'avis'
        verbose_name = 'Avis'
        verbose_name_plural = 'Avis'
        ordering = ['-created_at']
        unique_together = ['produit', 'client']
        indexes = [
            models.Index(fields=['produit', 'note']),
        ]
    
    def __str__(self):
        return f"Avis de {self.client.user.username} - {self.note}/5"

class MarketplaceArticleType(models.Model):
    """Type d'article administrable pour la marketplace."""
    KIND_CHOICES = (
        ('piece', 'Pièce détachée'),
        ('vehicle_sale', 'Véhicule à vendre'),
        ('vehicle_rental', 'Véhicule à louer'),
        ('service', 'Service'),
        ('other', 'Autre'),
    )

    code = models.SlugField(max_length=60, unique=True)
    label = models.CharField(max_length=120)
    kind = models.CharField(max_length=30, choices=KIND_CHOICES, default='piece')
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'marketplace_article_types'
        verbose_name = "Type d'article marketplace"
        verbose_name_plural = "Types d'articles marketplace"
        ordering = ['kind', 'label']

    def __str__(self):
        return self.label

class MarketplaceVehicle(models.Model):
    """Véhicules exposés dans la marketplace Cartronic (vente et location).

    Ce modèle est volontairement séparé du modèle apps.vehicles.Vehicle afin de ne
    pas impacter le module intervention_cartronic, qui gère les véhicules personnels
    des clients pour les interventions.
    """

    TYPE_CHOICES = (
        ('sale', 'Vente'),
        ('rental', 'Location'),
    )
    FUEL_CHOICES = (
        ('gazoil', 'Gazoil'),
        ('essence', 'Essence'),
        ('electrique', 'Électrique'),
        ('hybride', 'Hybride'),
    )
    TRANSMISSION_CHOICES = (
        ('manuel', 'Manuel'),
        ('automatique', 'Automatique'),
    )
    BODY_CHOICES = (
        ('berline', 'Berline'),
        ('suv', 'SUV'),
        ('pick-up', 'Pick-up'),
        ('monospace', 'Monospace'),
        ('citadine', 'Citadine'),
        ('cabriolet', 'Cabriolet'),
    )

    id = models.CharField(max_length=50, primary_key=True, editable=False)
    name = models.CharField(max_length=180, verbose_name='Nom commercial')
    brand = models.CharField(max_length=100, verbose_name='Marque')
    model = models.CharField(max_length=100, verbose_name='Modèle')
    year = models.IntegerField(validators=[MinValueValidator(1900), MaxValueValidator(2100)], verbose_name='Année')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='Type annonce')
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)], verbose_name='Prix')
    body_type = models.CharField(max_length=30, choices=BODY_CHOICES, default='berline', verbose_name='Carrosserie')
    transmission = models.CharField(max_length=30, choices=TRANSMISSION_CHOICES, default='manuel')
    fuel = models.CharField(max_length=30, choices=FUEL_CHOICES, default='essence', verbose_name='Carburant')
    seats = models.PositiveSmallIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(60)], verbose_name='Places')
    horsepower = models.PositiveIntegerField(default=0, verbose_name='Puissance')
    features = models.JSONField(default=list, blank=True, verbose_name='Équipements')
    location = models.CharField(max_length=150, blank=True, default='', verbose_name='Localisation')
    images = models.JSONField(default=list, blank=True, verbose_name='Images')
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(5)], verbose_name='Note moyenne')
    review_count = models.PositiveIntegerField(default=0, verbose_name="Nombre d'avis")
    partner = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='marketplace_vehicles', null=True, blank=True, limit_choices_to={'user_type__in': ['vendor', 'auto_shop', 'administrator']}, verbose_name='Partenaire')
    partner_name = models.CharField(max_length=150, blank=True, default='Cartronic', verbose_name='Nom partenaire')
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, verbose_name='Mis en avant')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'marketplace_vehicles'
        verbose_name = 'Véhicule marketplace'
        verbose_name_plural = 'Véhicules marketplace'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['type', 'is_active', 'is_featured']),
            models.Index(fields=['brand', 'model']),
            models.Index(fields=['price']),
            models.Index(fields=['location']),
        ]

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f"MVH-{uuid.uuid4().hex[:8].upper()}"
        if not self.name:
            self.name = f"{self.brand} {self.model}"
        super().save(*args, **kwargs)

    def __str__(self):
        suffix = '/jour' if self.type == 'rental' else ''
        return f"{self.name} - {self.price} FCFA{suffix}"

    @property
    def partner_display_name(self):
        if self.partner:
            return self.partner.get_full_name() or self.partner.username
        return self.partner_name or 'Cartronic'


class MarketplacePartnerApplication(models.Model):
    """Demande d'accréditation vendeur/boutique marketplace."""
    PARTNER_TYPES = (
        ('parts_seller', 'Vendeur de pièces / produits'),
        ('auto_shop', 'Boutique automobile / location'),
    )
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('approved', 'Approuvée'),
        ('rejected', 'Refusée'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='marketplace_partner_applications')
    partner_type = models.CharField(max_length=30, choices=PARTNER_TYPES)
    company_name = models.CharField(max_length=200)
    business_license = models.CharField(max_length=120, blank=True, default='')
    contact_phone = models.CharField(max_length=30, blank=True, default='')
    message = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True, default='')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_marketplace_applications')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'marketplace_partner_applications'
        verbose_name = "Demande partenaire marketplace"
        verbose_name_plural = "Demandes partenaires marketplace"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'partner_type']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"{self.company_name} ({self.get_partner_type_display()}) - {self.status}"

    def approve(self, admin_user=None):
        from apps.users.models import Vendor
        self.status = 'approved'
        self.rejection_reason = ''
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'rejection_reason', 'reviewed_by', 'reviewed_at', 'updated_at'])

        self.user.user_type = 'auto_shop' if self.partner_type == 'auto_shop' else 'vendor'
        self.user.is_active = True
        self.user.save(update_fields=['user_type', 'is_active', 'updated_at'])

        profile, _ = Vendor.objects.get_or_create(user=self.user)
        profile.partner_type = self.partner_type
        profile.company_name = self.company_name
        profile.business_license = self.business_license
        profile.approval_status = 'approved'
        profile.rejection_reason = ''
        profile.is_verified = True
        profile.approved_at = timezone.now()
        profile.approved_by = admin_user
        profile.save(update_fields=[
            'partner_type', 'company_name', 'business_license', 'approval_status',
            'rejection_reason', 'is_verified', 'approved_at', 'approved_by'
        ])
        return profile

    def reject(self, admin_user=None, reason=''):
        from apps.users.models import Vendor
        self.status = 'rejected'
        self.rejection_reason = reason or ''
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'rejection_reason', 'reviewed_by', 'reviewed_at', 'updated_at'])
        try:
            profile = self.user.vendor_profile
            profile.approval_status = 'rejected'
            profile.rejection_reason = self.rejection_reason
            profile.is_verified = False
            profile.save(update_fields=['approval_status', 'rejection_reason', 'is_verified'])
        except Vendor.DoesNotExist:
            pass


class MarketplaceOrder(models.Model):
    """Commandes de la marketplace mobile (pièces, achat véhicule, location véhicule)."""

    TYPE_CHOICES = (
        ('vehicle_sale', 'Achat véhicule'),
        ('vehicle_rental', 'Location véhicule'),
        ('part', 'Pièces détachées'),
    )
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('confirmed', 'Confirmée'),
        ('ready', 'Prête'),
        ('in_progress', 'En cours'),
        ('overdue', 'En retard'),
        ('delivered', 'Livrée'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée'),
        ('refunded', 'Remboursée'),
    )
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('paid', 'Payée'),
        ('partially_paid', 'Partiellement payée'),
        ('refunded', 'Remboursée'),
    )
    PAYMENT_METHOD_CHOICES = (
        ('cash', 'Espèces'),
        ('card', 'Carte'),
        ('orange_money', 'Orange Money'),
        ('mobile_money', 'Mobile Money'),
    )

    id = models.CharField(max_length=50, primary_key=True, editable=False)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, related_name='marketplace_orders', null=True, blank=True)
    marketplace_user = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='marketplace_orders', null=True, blank=True)
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=30, choices=PAYMENT_STATUS_CHOICES, default='pending')
    items = models.JSONField(default=list, blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    currency = models.CharField(max_length=10, default='CFA')
    rental_start_date = models.DateTimeField(null=True, blank=True)
    rental_end_date = models.DateTimeField(null=True, blank=True)
    actual_pickup_date = models.DateTimeField(null=True, blank=True)
    actual_return_date = models.DateTimeField(null=True, blank=True)
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, blank=True, default='')
    payment_date = models.DateTimeField(null=True, blank=True)
    shipping_address = models.JSONField(default=dict, blank=True)
    shipping_method = models.JSONField(default=dict, blank=True)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True, default='')
    cancellation_reason = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'marketplace_orders'
        verbose_name = 'Commande marketplace mobile'
        verbose_name_plural = 'Commandes marketplace mobile'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['marketplace_user', 'status']),
            models.Index(fields=['type', 'status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['created_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f"MORD-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Commande marketplace {self.id} - {self.marketplace_user.username if self.marketplace_user else (self.client.user.username if self.client else 'client supprimé')}"

