from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.gis.admin import GISModelAdmin
from apps.users.models import User, Client, Technician, Vendor, Administrator


@admin.register(User)
class UserAdmin(BaseUserAdmin, GISModelAdmin):
    """Admin pour le modèle User avec support géographique"""
    list_display = ['username', 'email', 'user_type', 'telephone', 'is_available', 'is_active', 'date_joined']
    list_filter = ['user_type', 'is_available', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'telephone', 'first_name', 'last_name']
    ordering = ['-date_joined']
    list_per_page = 25
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Informations supplémentaires', {
            'fields': ('user_type', 'telephone', 'location', 'is_available')
        }),
        ('Dates importantes', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'date_joined', 'last_login']
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Informations supplémentaires', {
            'fields': ('user_type', 'telephone', 'email', 'first_name', 'last_name')
        }),
    )


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """Admin pour les clients"""
    list_display = ['id', 'get_username', 'get_email', 'get_telephone', 'get_total_reservations', 'created_at']
    search_fields = ['user__username', 'user__email', 'user__telephone']
    list_filter = ['user__date_joined']
    readonly_fields = ['historique_commandes']
    list_per_page = 25
    
    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Username'
    get_username.admin_order_field = 'user__username'
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    get_email.admin_order_field = 'user__email'
    
    def get_telephone(self, obj):
        return obj.user.telephone
    get_telephone.short_description = 'Téléphone'
    
    def get_total_reservations(self, obj):
        return obj.reservations.count()
    get_total_reservations.short_description = 'Réservations'
    
    def created_at(self, obj):
        return obj.user.date_joined
    created_at.short_description = 'Date d\'inscription'
    created_at.admin_order_field = 'user__date_joined'


@admin.register(Technician)
class TechnicianAdmin(admin.ModelAdmin):
    """Admin pour les techniciens"""
    list_display = ['id', 'get_username', 'status', 'rating', 'total_interventions', 'get_specializations', 'is_available']
    list_filter = ['status', 'rating', 'user__is_available']
    search_fields = ['user__username', 'user__email', 'user__telephone']
    ordering = ['-rating', '-total_interventions']
    list_per_page = 25
    
    fieldsets = (
        ('Informations utilisateur', {
            'fields': ('user',)
        }),
        ('Profil professionnel', {
            'fields': ('certifications', 'specializations', 'status')
        }),
        ('Performances', {
            'fields': ('rating', 'total_interventions')
        }),
    )
    
    readonly_fields = ['rating', 'total_interventions']
    
    def get_username(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_username.short_description = 'Technicien'
    get_username.admin_order_field = 'user__username'
    
    def get_specializations(self, obj):
        return ', '.join(obj.specializations) if obj.specializations else '-'
    get_specializations.short_description = 'Spécialisations'
    
    def is_available(self, obj):
        return obj.user.is_available
    is_available.boolean = True
    is_available.short_description = 'Disponible'


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    """Admin pour les vendeurs"""
    list_display = ['id', 'get_username', 'company_name', 'rating', 'total_sales', 'is_verified', 'created_at']
    list_filter = ['is_verified', 'user__date_joined']
    search_fields = ['user__username', 'user__email', 'company_name', 'business_license']
    ordering = ['-total_sales', '-rating']
    list_per_page = 25
    
    fieldsets = (
        ('Informations utilisateur', {
            'fields': ('user',)
        }),
        ('Informations entreprise', {
            'fields': ('company_name', 'business_license', 'is_verified')
        }),
        ('Performances', {
            'fields': ('rating', 'total_sales')
        }),
    )
    
    readonly_fields = ['rating', 'total_sales']
    
    actions = ['verify_vendors']
    
    def get_username(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_username.short_description = 'Vendeur'
    get_username.admin_order_field = 'user__username'
    
    def created_at(self, obj):
        return obj.user.date_joined
    created_at.short_description = 'Date d\'inscription'
    created_at.admin_order_field = 'user__date_joined'
    
    def verify_vendors(self, request, queryset):
        """Action pour vérifier plusieurs vendeurs"""
        count = queryset.update(is_verified=True)
        self.message_user(request, f'{count} vendeur(s) vérifié(s) avec succès.')
    verify_vendors.short_description = 'Vérifier les vendeurs sélectionnés'


@admin.register(Administrator)
class AdministratorAdmin(admin.ModelAdmin):
    """Admin pour les administrateurs"""
    list_display = ['id', 'get_username', 'get_email', 'department', 'created_at']
    search_fields = ['user__username', 'user__email', 'department']
    list_filter = ['user__date_joined']
    list_per_page = 25
    
    fieldsets = (
        ('Informations utilisateur', {
            'fields': ('user',)
        }),
        ('Informations administrateur', {
            'fields': ('department', 'permissions')
        }),
    )
    
    def get_username(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_username.short_description = 'Administrateur'
    get_username.admin_order_field = 'user__username'
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    get_email.admin_order_field = 'user__email'
    
    def created_at(self, obj):
        return obj.user.date_joined
    created_at.short_description = 'Date d\'inscription'
    created_at.admin_order_field = 'user__date_joined'


# Personnalisation du site admin
admin.site.site_header = "Administration Technicien Platform"
admin.site.site_title = "Technicien Admin"
admin.site.index_title = "Bienvenue dans l'interface d'administration"