from django.db import models
from django.contrib.gis.db import models as gis_models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.users.models import Client, Technician, User
from apps.vehicles.models import Vehicle  # Import depuis vehicles


class Reservation(models.Model):
    """Réservations de techniciens"""
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('confirmed', 'Confirmée'),
        ('technician_dispatched', 'Technicien en route'),
        ('technician_arrived', 'Technicien arrivé'),
        ('in_progress', 'En cours'),
        ('diagnosis_submitted', 'Diagnostic soumis'),
        ('awaiting_client_approval', 'En attente approbation client'),
        ('parts_ordered', 'Pièces commandées'),
        ('ready_for_pickup', 'Prêt pour récupération'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée'),
    )
    
    SERVICE_TYPES = (
        ('emergency', 'Panne urgente'),
        ('diagnosis', 'Diagnostic'),
        ('roadside_repair', 'Dépannage sur place'),
        ('towing', 'Remorquage'),
        ('scheduled_maintenance', 'Révision planifiée'),
        ('specific_repair', 'Réparation spécifique'),
        ('preventive_maintenance', 'Entretien préventif'),
    )
    
    URGENCY_LEVELS = (
        ('low', 'Normal'),
        ('medium', 'Important'),
        ('high', 'Urgent'),
        ('critical', 'Critique'),
    )
    
    # Relations
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='reservations')
    technician = models.ForeignKey(
        Technician, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='reservations'
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reservations'
    )
    
    # Informations de base
    service_type = models.CharField(max_length=30, choices=SERVICE_TYPES)
    intervention_type = models.CharField(
        max_length=100, 
        verbose_name="Type d'intervention",
        blank=True,
        default='diagnostic_general'
    )
    urgency_level = models.CharField(max_length=20, choices=URGENCY_LEVELS, default='low')
    
    # Date et heure
    date = models.DateTimeField(verbose_name="Date et heure de l'intervention")
    scheduled_end_time = models.DateTimeField(null=True, blank=True)
    actual_start_time = models.DateTimeField(null=True, blank=True)
    actual_end_time = models.DateTimeField(null=True, blank=True)
    
    # Statut et localisation
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    description = models.TextField(verbose_name="Description du problème")
    location = gis_models.PointField(srid=4326, verbose_name="Localisation")
    location_description = models.CharField(max_length=255, blank=True, verbose_name="Description lieu")
    
    # Symptômes guidés
    symptoms = models.JSONField(default=list, blank=True)
    dashboard_warnings = models.JSONField(default=list, blank=True)
    can_restart = models.BooleanField(null=True, blank=True)
    photos = models.JSONField(default=list, blank=True)
    
    # Tarification
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estimated_price_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estimated_price_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    deposit_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Services additionnels
    includes_towing = models.BooleanField(default=False)
    towing_distance_km = models.FloatField(null=True, blank=True)
    towing_destination = models.CharField(max_length=255, blank=True)
    
    # Communication
    notes = models.TextField(blank=True)
    client_notified_arrival = models.BooleanField(default=False)
    client_notified_diagnosis = models.BooleanField(default=False)
    client_notified_completion = models.BooleanField(default=False)
    
    warranty_months = models.IntegerField(default=0)
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cancelled_reservations')
    cancellation_reason = models.TextField(blank=True)
    
    class Meta:
        db_table = 'reservations'
        verbose_name = 'Réservation'
        verbose_name_plural = 'Réservations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'date']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['technician', 'status']),
            models.Index(fields=['service_type', 'urgency_level']),
        ]
    
    def __str__(self):
        return f"Réservation #{self.id} - {self.client.user.username} - {self.get_status_display()}"
    
    @property
    def is_emergency(self):
        return self.service_type == 'emergency' or self.urgency_level in ['high', 'critical']
    
    @property
    def is_completed(self):
        return self.status == 'completed'
    
    @property
    def is_cancelled(self):
        return self.status == 'cancelled'
    
    @property
    def can_be_cancelled(self):
        return self.status in ['pending', 'confirmed']
    
    @property
    def requires_client_approval(self):
        return self.status == 'awaiting_client_approval'


class TripTracking(models.Model):
    """Suivi en temps réel du trajet"""
    STATUS_CHOICES = (
        ('not_started', 'Non démarré'),
        ('en_route', 'En route'),
        ('arrived', 'Arrivé'),
    )
    
    reservation = models.OneToOneField(Reservation, on_delete=models.CASCADE, related_name='trip_tracking')
    technician_current_location = gis_models.PointField(srid=4326, null=True, blank=True)
    
    estimated_arrival_time = models.DateTimeField(null=True, blank=True)
    distance_remaining_km = models.FloatField(null=True, blank=True)
    travel_duration_minutes = models.IntegerField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    
    started_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    
    location_history = models.JSONField(default=list)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'trip_tracking'
        verbose_name = 'Suivi de trajet'
        verbose_name_plural = 'Suivis de trajet'
    
    def __str__(self):
        return f"Trajet #{self.reservation.id} - {self.status}"


class Diagnostic(models.Model):
    """Diagnostic détaillé"""
    SEVERITY_CHOICES = (
        ('minor', 'Mineur'),
        ('moderate', 'Modéré'),
        ('severe', 'Sévère'),
        ('critical', 'Critique'),
    )
    
    REPAIR_LOCATION_CHOICES = (
        ('onsite', 'Sur place'),
        ('workshop', 'En atelier'),
        ('specialized', 'Atelier spécialisé'),
    )
    
    reservation = models.OneToOneField(Reservation, on_delete=models.CASCADE, related_name='diagnostic')
    technician = models.ForeignKey(Technician, on_delete=models.CASCADE)
    
    identified_issue = models.CharField(max_length=200)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    
    symptoms_found = models.JSONField(default=list)
    obd_codes = models.JSONField(default=list)
    parts_needed = models.JSONField(default=list)
    
    estimated_repair_time_hours = models.FloatField()
    estimated_labor_cost = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_parts_cost = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    
    can_repair_onsite = models.BooleanField(default=False)
    recommended_repair_location = models.CharField(max_length=20, choices=REPAIR_LOCATION_CHOICES)
    repair_location_reason = models.TextField(blank=True)
    
    photos = models.JSONField(default=list)
    videos = models.JSONField(default=list)
    
    detailed_report = models.TextField()
    recommendations = models.TextField(blank=True)
    
    requires_immediate_attention = models.BooleanField(default=False)
    safe_to_drive = models.BooleanField(default=True)
    
    client_approved = models.BooleanField(null=True, blank=True)
    client_approval_date = models.DateTimeField(null=True, blank=True)
    client_comments = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'diagnostics'
        verbose_name = 'Diagnostic'
        verbose_name_plural = 'Diagnostics'
    
    def __str__(self):
        return f"Diagnostic #{self.reservation.id} - {self.identified_issue}"


class WorkProgress(models.Model):
    """Suivi de l'avancement"""
    STATUS_CHOICES = (
        ('inspection', 'Inspection initiale'),
        ('diagnosis', 'Diagnostic en cours'),
        ('parts_ordering', 'Commande de pièces'),
        ('parts_received', 'Pièces reçues'),
        ('repair_in_progress', 'Réparation en cours'),
        ('testing', 'Tests et réglages'),
        ('completed', 'Travaux terminés'),
    )
    
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='work_progress')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES)
    description = models.TextField()
    
    photos = models.JSONField(default=list)
    videos = models.JSONField(default=list)
    
    client_notified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'work_progress'
        verbose_name = 'Avancement travaux'
        verbose_name_plural = 'Avancements travaux'
        ordering = ['created_at']


class ChatConversation(models.Model):
    """Conversation liée à une réservation"""
    reservation = models.OneToOneField(Reservation, on_delete=models.CASCADE, related_name='conversation')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chat_conversations'


class ChatMessage(models.Model):
    """Messages de chat"""
    MESSAGE_TYPES = (
        ('text', 'Texte'),
        ('image', 'Image'),
        ('location', 'Position GPS'),
        ('file', 'Fichier'),
    )
    
    conversation = models.ForeignKey(ChatConversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField()
    attachment_url = models.URLField(blank=True)
    location = gis_models.PointField(srid=4326, null=True, blank=True)
    
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chat_messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
        ]


class TechnicianAvailability(models.Model):
    """Créneaux de disponibilité"""
    technician = models.ForeignKey(Technician, on_delete=models.CASCADE, related_name='availabilities')
    
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    is_available = models.BooleanField(default=True)
    max_bookings = models.IntegerField(default=1)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'technician_availabilities'
        unique_together = ('technician', 'date', 'start_time')
        ordering = ['date', 'start_time']


class Invoice(models.Model):
    """Factures détaillées"""
    PAYMENT_STATUS = (
        ('pending', 'En attente'),
        ('partial', 'Partiellement payée'),
        ('paid', 'Payée'),
        ('refunded', 'Remboursée'),
    )
    
    reservation = models.OneToOneField(Reservation, on_delete=models.CASCADE, related_name='invoice')
    
    towing_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    diagnosis_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    parts_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    labor_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=10, decimal_places=2)
    
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    line_items = models.JSONField(default=list)
    
    warranty_months_parts = models.IntegerField(default=0)
    warranty_months_labor = models.IntegerField(default=0)
    
    notes = models.TextField(blank=True)
    
    issued_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'invoices'


class Evaluation(models.Model):
    """Évaluations des prestations"""
    reservation = models.OneToOneField(Reservation, on_delete=models.CASCADE, related_name='evaluation')
    note = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    commentaire = models.TextField(blank=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='evaluations')
    technician = models.ForeignKey(Technician, on_delete=models.CASCADE, related_name='evaluations')
    
    # Critères détaillés
    response_time_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    diagnosis_quality_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    communication_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    professionalism = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    value_for_money = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    
    # Colonnes anciennes (compatibilité)
    punctuality = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    quality = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    
    would_recommend = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'evaluations'
        verbose_name = 'Évaluation'
        verbose_name_plural = 'Évaluations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['technician', 'note']),
        ]
    
    def __str__(self):
        return f"Évaluation {self.note}/5 - {self.technician.user.username}"