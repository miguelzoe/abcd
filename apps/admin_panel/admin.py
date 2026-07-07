from django.contrib import admin
from apps.admin_panel.models import Signalement, Notification


@admin.register(Signalement)
class SignalementAdmin(admin.ModelAdmin):
    list_display = ['id', 'contenu', 'type', 'status', 'nombre_fois_signale', 'created_at']
    list_filter = ['status', 'type']
    search_fields = ['contenu', 'raison', 'signale_par_nom']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'destinataire', 'type', 'titre', 'lu', 'created_at']
    list_filter = ['type', 'lu']
    search_fields = ['titre', 'message', 'destinataire__username']
    readonly_fields = ['created_at']
    ordering = ['-created_at']