import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class VoiceCallSession(models.Model):
    """Session d'appel vocal interne à l'application.

    La voix passe en pair-à-pair WebRTC entre les deux mobiles. Le serveur ne transporte
    pas l'audio : il authentifie l'appel, stocke l'historique et relaie uniquement les
    messages de signalisation (offer/answer/ICE/status).
    """

    STATUS_RINGING = 'ringing'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_MISSED = 'missed'
    STATUS_ENDED = 'ended'
    STATUS_CANCELLED = 'cancelled'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = (
        (STATUS_RINGING, 'Sonnerie'),
        (STATUS_ACCEPTED, 'Accepté'),
        (STATUS_REJECTED, 'Refusé'),
        (STATUS_MISSED, 'Manqué'),
        (STATUS_ENDED, 'Terminé'),
        (STATUS_CANCELLED, 'Annulé'),
        (STATUS_FAILED, 'Échec'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reservation = models.ForeignKey(
        'reservations.Reservation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='voice_calls',
    )
    caller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='outgoing_voice_calls',
    )
    callee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='incoming_voice_calls',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RINGING)
    started_at = models.DateTimeField(default=timezone.now)
    answered_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    end_reason = models.CharField(max_length=120, blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'voice_call_sessions'
        ordering = ['-created_at']
        verbose_name = 'Session appel vocal'
        verbose_name_plural = 'Sessions appels vocaux'
        indexes = [
            models.Index(fields=['caller', 'status', 'created_at']),
            models.Index(fields=['callee', 'status', 'created_at']),
            models.Index(fields=['reservation', 'created_at']),
        ]

    def __str__(self):
        return f"Appel {self.id} • {self.caller_id} → {self.callee_id} • {self.status}"

    @property
    def is_open(self):
        return self.status in {self.STATUS_RINGING, self.STATUS_ACCEPTED}

    def mark_accepted(self):
        if self.status != self.STATUS_ACCEPTED:
            self.status = self.STATUS_ACCEPTED
            self.answered_at = timezone.now()
            self.save(update_fields=['status', 'answered_at', 'updated_at'])

    def mark_terminal(self, status, reason=''):
        now = timezone.now()
        self.status = status
        self.ended_at = now
        self.end_reason = reason or self.end_reason
        if self.answered_at:
            self.duration_seconds = max(0, int((now - self.answered_at).total_seconds()))
        self.save(update_fields=['status', 'ended_at', 'duration_seconds', 'end_reason', 'updated_at'])


class VoiceCallSignal(models.Model):
    """Trace des messages de signalisation WebRTC échangés pendant un appel."""

    SIGNAL_TYPES = (
        ('offer', 'Offer SDP'),
        ('answer', 'Answer SDP'),
        ('ice-candidate', 'ICE candidate'),
        ('ringing', 'Sonnerie'),
        ('accepted', 'Accepté'),
        ('rejected', 'Refusé'),
        ('ended', 'Terminé'),
        ('failed', 'Échec'),
        ('mute-state', 'État micro'),
    )

    session = models.ForeignKey(VoiceCallSession, on_delete=models.CASCADE, related_name='signals')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='voice_signals')
    signal_type = models.CharField(max_length=40, choices=SIGNAL_TYPES)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'voice_call_signals'
        ordering = ['created_at']
        verbose_name = 'Signal appel vocal'
        verbose_name_plural = 'Signaux appels vocaux'
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['sender', 'signal_type']),
        ]

    def __str__(self):
        return f"{self.signal_type} • {self.session_id} • {self.sender_id}"
