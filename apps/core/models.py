from django.db import models
from apps.users.models import User

class Interaction(models.Model):
    """Interactions/Messages"""
    id = models.CharField(max_length=50, primary_key=True)
    date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default='sent')
    contenu = models.TextField()
    expediteur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages_envoyes')
    destinataire = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages_recus')
    
    class Meta:
        db_table = 'interactions'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['expediteur', 'destinataire']),
        ]