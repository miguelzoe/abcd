from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Vehicle(models.Model):
    """Véhicules des clients - MODÈLE UNIFIÉ"""
    TYPE_CHOICES = (
        ('sedan', 'Berline'),
        ('suv', 'SUV'),
        ('pickup', 'Pick-up'),
        ('van', 'Fourgonnette'),
        ('motorcycle', 'Moto'),
        ('truck', 'Camion'),
        ('autre', 'Autre'),
    )
    
    STATUS_CHOICES = (
        ('actif', 'Actif'),
        ('inactif', 'Inactif'),
        ('en_reparation', 'En réparation'),
        ('vendu', 'Vendu'),
    )
    
    # Relations - Support simple ET multiple propriétaires
    client = models.ForeignKey(
        'users.Client',
        on_delete=models.CASCADE,
        related_name='vehicles',
        verbose_name="Propriétaire principal"
    )
    proprietaires = models.ManyToManyField(
        'users.Client',
        related_name='vehicules',
        blank=True,
        verbose_name="Co-propriétaires"
    )
    
    # Informations de base
    brand = models.CharField(max_length=100, verbose_name="Marque", db_column='marque')
    model = models.CharField(max_length=100, verbose_name="Modèle", db_column='modele')
    vehicle_type = models.CharField(
        max_length=50, 
        choices=TYPE_CHOICES, 
        default='sedan',
        verbose_name="Type de véhicule",
        db_column='type_vehicule'
    )
    year = models.IntegerField(
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
        verbose_name="Année",
        db_column='annee'
    )
    
    # Détails techniques
    color = models.CharField(
        max_length=50, 
        blank=True, 
        verbose_name="Couleur",
        db_column='couleur'
    )
    license_plate = models.CharField(
        max_length=50, 
        unique=True,
        blank=True,
        null=True,
        verbose_name="Numéro d'immatriculation",
        db_column='numero_immatriculation'
    )
    vin = models.CharField(
        max_length=100, 
        unique=True,
        blank=True,
        null=True,
        verbose_name="Numéro de châssis (VIN)",
        db_column='numero_chassis'
    )
    mileage = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Kilométrage",
        db_column='kilometrage'
    )
    
    # Informations financières
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
        verbose_name="Prix d'achat",
        db_column='prix'
    )
    status = models.CharField(
        max_length=50, 
        choices=STATUS_CHOICES,
        default='actif',
        verbose_name="Statut",
        db_column='statut'
    )
    
    # Entretien
    last_service_date = models.DateField(
        null=True, 
        blank=True,
        verbose_name="Date dernier entretien"
    )
    last_service_mileage = models.IntegerField(
        null=True, 
        blank=True,
        verbose_name="Kilométrage dernier entretien"
    )
    
    # Notes
    notes = models.TextField(blank=True, verbose_name="Notes")
    
    # État
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vehicles'
        verbose_name = 'Véhicule'
        verbose_name_plural = 'Véhicules'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['brand', 'model']),
            models.Index(fields=['license_plate']),
            models.Index(fields=['status']),
            models.Index(fields=['vehicle_type']),
        ]
    
    def __str__(self):
        return f"{self.brand} {self.model} ({self.year})"
    
    @property
    def marque(self):
        """Compatibilité avec l'ancien code"""
        return self.brand
    
    @property
    def modele(self):
        """Compatibilité avec l'ancien code"""
        return self.model
    
    @property
    def annee(self):
        """Compatibilité avec l'ancien code"""
        return self.year
    
    @property
    def type_vehicule(self):
        """Compatibilité avec l'ancien code"""
        return self.vehicle_type
    
    @property
    def kilometrage(self):
        """Compatibilité avec l'ancien code"""
        return self.mileage
    
    @property
    def numero_immatriculation(self):
        """Compatibilité avec l'ancien code"""
        return self.license_plate
    
    @property
    def numero_chassis(self):
        """Compatibilité avec l'ancien code"""
        return self.vin
    
    @property
    def couleur(self):
        """Compatibilité avec l'ancien code"""
        return self.color
    
    @property
    def prix(self):
        """Compatibilité avec l'ancien code"""
        return self.price
    
    @property
    def statut(self):
        """Compatibilité avec l'ancien code"""
        return self.status
    
    @property
    def full_name(self):
        """Nom complet du véhicule"""
        return f"{self.brand} {self.model} {self.year}"
    
    @property
    def age(self):
        """Âge du véhicule en années"""
        from datetime import datetime
        return datetime.now().year - self.year
    
    @property
    def next_service_due(self):
        """Calculer le prochain service basé sur kilométrage"""
        if self.last_service_mileage:
            intervals = [20000, 40000, 60000, 80000, 100000]
            for interval in intervals:
                if self.last_service_mileage < interval:
                    return interval
        return None


class MaintenanceRecord(models.Model):
    """Historique de maintenance des véhicules"""
    TYPE_CHOICES = (
        ('vidange', 'Vidange'),
        ('revision', 'Révision'),
        ('reparation', 'Réparation'),
        ('diagnostic', 'Diagnostic'),
        ('entretien', 'Entretien'),
        ('autre', 'Autre'),
    )
    
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='maintenance_records',
        verbose_name="Véhicule"
    )
    date = models.DateTimeField(verbose_name="Date de l'intervention")
    type_maintenance = models.CharField(
        max_length=50,
        choices=TYPE_CHOICES,
        verbose_name="Type de maintenance"
    )
    description = models.TextField(verbose_name="Description")
    cout = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Coût"
    )
    kilometrage_actuel = models.IntegerField(
        validators=[MinValueValidator(0)],
        verbose_name="Kilométrage au moment de l'intervention"
    )
    
    # Technicien (optionnel)
    technician = models.ForeignKey(
        'users.Technician',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_done',
        verbose_name="Technicien"
    )
    
    # Notes
    notes = models.TextField(blank=True, verbose_name="Notes additionnelles")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'maintenance_records'
        verbose_name = 'Historique de maintenance'
        verbose_name_plural = 'Historiques de maintenance'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['vehicle', 'date']),
            models.Index(fields=['type_maintenance']),
        ]
    
    def __str__(self):
        return f"{self.get_type_maintenance_display()} - {self.vehicle.full_name} - {self.date.strftime('%d/%m/%Y')}"