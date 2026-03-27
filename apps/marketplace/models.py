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
        limit_choices_to={'user_type__in': ['vendor', 'administrator']},
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