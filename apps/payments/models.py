from django.db import models
from django.utils import timezone


class PaymentTransaction(models.Model):
    KIND_CHOICES = (
        ('deposit', 'Dépôt'),
        ('final', 'Frais intervention'),
    )
    PROVIDER_CHOICES = (
        ('momo', 'MTN Mobile Money'),
        ('om', 'Orange Money'),
    )
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('confirmed', 'Confirmé'),
        ('failed', 'Échoué'),
        ('cancelled', 'Annulé'),
    )

    reservation = models.ForeignKey('reservations.Reservation', on_delete=models.CASCADE, related_name='payments')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    provider = models.CharField(max_length=10, choices=PROVIDER_CHOICES)
    phone_number = models.CharField(max_length=32)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    external_reference = models.CharField(max_length=64, blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'payment_transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reservation', 'kind', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.kind} {self.amount} {self.provider} ({self.status})"
