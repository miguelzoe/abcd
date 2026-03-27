from django.contrib import admin
from apps.vehicles.models import Vehicle, MaintenanceRecord


class MaintenanceRecordInline(admin.TabularInline):
    """Inline pour afficher les maintenances dans le véhicule"""
    model = MaintenanceRecord
    extra = 0
    fields = ['date', 'type_maintenance', 'cout', 'kilometrage_actuel', 'technician']
    readonly_fields = ['date']
    ordering = ['-date']
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    """Admin pour les véhicules"""
    list_display = [
        'id', 'full_name', 'vehicle_type', 'year', 'license_plate',
        'mileage', 'status', 'get_proprietaires_count', 'created_at'
    ]
    # CORRECTION ICI : Utiliser les vrais noms de champs, pas les properties
    list_filter = ['vehicle_type', 'status', 'brand', 'year', 'created_at']
    
    search_fields = [
        'brand', 'model', 'license_plate', 'vin',
        'proprietaires__user__username', 'proprietaires__user__email'
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    list_per_page = 25
    filter_horizontal = ['proprietaires']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('brand', 'model', 'vehicle_type', 'year', 'color')
        }),
        ('Identification', {
            'fields': ('license_plate', 'vin')
        }),
        ('Détails techniques', {
            'fields': ('mileage', 'price', 'status')
        }),
        ('Propriétaires', {
            'fields': ('client', 'proprietaires')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    inlines = [MaintenanceRecordInline]
    
    actions = ['mark_as_active', 'mark_as_inactive', 'mark_as_reparation']
    
    def get_proprietaires_count(self, obj):
        return obj.proprietaires.count()
    get_proprietaires_count.short_description = 'Propriétaires'
    
    def mark_as_active(self, request, queryset):
        """Action pour marquer comme actif"""
        count = queryset.update(status='actif')
        self.message_user(request, f'{count} véhicule(s) marqué(s) comme actif.')
    mark_as_active.short_description = 'Marquer comme actif'
    
    def mark_as_inactive(self, request, queryset):
        """Action pour marquer comme inactif"""
        count = queryset.update(status='inactif')
        self.message_user(request, f'{count} véhicule(s) marqué(s) comme inactif.')
    mark_as_inactive.short_description = 'Marquer comme inactif'
    
    def mark_as_reparation(self, request, queryset):
        """Action pour marquer en réparation"""
        count = queryset.update(status='en_reparation')
        self.message_user(request, f'{count} véhicule(s) marqué(s) en réparation.')
    mark_as_reparation.short_description = 'Marquer en réparation'


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    """Admin pour les maintenances"""
    list_display = [
        'id', 'get_vehicle_name', 'date', 'type_maintenance',
        'cout', 'kilometrage_actuel', 'get_technician_name', 'created_at'
    ]
    list_filter = ['type_maintenance', 'date', 'created_at']
    search_fields = [
        'vehicle__brand', 'vehicle__model', 'vehicle__license_plate',
        'description', 'technician__user__username'
    ]
    ordering = ['-date']
    date_hierarchy = 'date'
    list_per_page = 25
    
    fieldsets = (
        ('Véhicule', {
            'fields': ('vehicle',)
        }),
        ('Intervention', {
            'fields': ('date', 'type_maintenance', 'description', 'technician')
        }),
        ('Détails', {
            'fields': ('cout', 'kilometrage_actuel', 'notes')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def get_vehicle_name(self, obj):
        return obj.vehicle.full_name
    get_vehicle_name.short_description = 'Véhicule'
    get_vehicle_name.admin_order_field = 'vehicle__brand'
    
    def get_technician_name(self, obj):
        if obj.technician:
            return obj.technician.user.get_full_name() or obj.technician.user.username
        return '-'
    get_technician_name.short_description = 'Technicien'
    get_technician_name.admin_order_field = 'technician__user__username'