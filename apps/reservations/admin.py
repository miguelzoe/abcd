from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from apps.reservations.models import Reservation, Evaluation


@admin.register(Reservation)
class ReservationAdmin(GISModelAdmin):
    """Admin pour les réservations avec support géographique"""
    list_display = [
        'id', 'get_client', 'get_technician', 'date', 'status',
        'intervention_type', 'price', 'has_evaluation', 'created_at'
    ]
    list_filter = ['status', 'intervention_type', 'date', 'created_at']
    search_fields = [
        'client__user__username', 'client__user__email',
        'technician__user__username', 'technician__user__email',
        'description', 'intervention_type'
    ]
    ordering = ['-created_at']
    date_hierarchy = 'date'
    list_per_page = 25
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('client', 'technician', 'date', 'status')
        }),
        ('Détails de l\'intervention', {
            'fields': ('intervention_type', 'description', 'location', 'price', 'notes')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    actions = ['mark_as_confirmed', 'mark_as_completed', 'mark_as_cancelled']
    
    def get_client(self, obj):
        return obj.client.user.get_full_name() or obj.client.user.username
    get_client.short_description = 'Client'
    get_client.admin_order_field = 'client__user__username'
    
    def get_technician(self, obj):
        if obj.technician:
            return obj.technician.user.get_full_name() or obj.technician.user.username
        return '-'
    get_technician.short_description = 'Technicien'
    get_technician.admin_order_field = 'technician__user__username'
    
    def has_evaluation(self, obj):
        return hasattr(obj, 'evaluation')
    has_evaluation.boolean = True
    has_evaluation.short_description = 'Évaluée'
    
    def mark_as_confirmed(self, request, queryset):
        """Action pour confirmer plusieurs réservations"""
        count = queryset.update(status='confirmed')
        self.message_user(request, f'{count} réservation(s) confirmée(s).')
    mark_as_confirmed.short_description = 'Marquer comme confirmée'
    
    def mark_as_completed(self, request, queryset):
        """Action pour terminer plusieurs réservations"""
        count = queryset.update(status='completed')
        self.message_user(request, f'{count} réservation(s) terminée(s).')
    mark_as_completed.short_description = 'Marquer comme terminée'
    
    def mark_as_cancelled(self, request, queryset):
        """Action pour annuler plusieurs réservations"""
        count = queryset.update(status='cancelled')
        self.message_user(request, f'{count} réservation(s) annulée(s).')
    mark_as_cancelled.short_description = 'Annuler'


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    """Admin pour les évaluations"""
    list_display = [
        'id', 'get_reservation_id', 'get_client', 'get_technician',
        'note', 'punctuality', 'professionalism', 'quality', 'created_at'
    ]
    list_filter = ['note', 'punctuality', 'professionalism', 'quality', 'created_at']
    search_fields = [
        'client__user__username', 'technician__user__username',
        'commentaire', 'reservation__id'
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    list_per_page = 25
    
    fieldsets = (
        ('Réservation', {
            'fields': ('reservation',)
        }),
        ('Participants', {
            'fields': ('client', 'technician')
        }),
        ('Évaluation', {
            'fields': ('note', 'commentaire')
        }),
        ('Détails', {
            'fields': ('punctuality', 'professionalism', 'quality'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'client', 'technician', 'reservation']
    
    def get_reservation_id(self, obj):
        return f"#{obj.reservation.id}"
    get_reservation_id.short_description = 'Réservation'
    get_reservation_id.admin_order_field = 'reservation__id'
    
    def get_client(self, obj):
        return obj.client.user.get_full_name() or obj.client.user.username
    get_client.short_description = 'Client'
    get_client.admin_order_field = 'client__user__username'
    
    def get_technician(self, obj):
        return obj.technician.user.get_full_name() or obj.technician.user.username
    get_technician.short_description = 'Technicien'
    get_technician.admin_order_field = 'technician__user__username'