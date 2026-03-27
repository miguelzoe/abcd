from django.contrib import admin
from apps.marketplace.models import Produit, Piece, Commande, LigneCommande, Avis


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    """Admin pour les produits"""
    list_display = [
        'id', 'nom', 'category', 'prix', 'stock', 'vendeur',
        'is_active', 'is_featured', 'created_at'
    ]
    list_filter = ['category', 'is_active', 'is_featured', 'created_at']
    search_fields = ['nom', 'description', 'marque', 'reference', 'vendeur__username']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'description', 'prix', 'stock', 'category')
        }),
        ('Détails', {
            'fields': ('marque', 'reference', 'images', 'vendeur')
        }),
        ('Statut', {
            'fields': ('is_active', 'is_featured')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    actions = ['mark_as_active', 'mark_as_inactive', 'mark_as_featured']
    
    def mark_as_active(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} produit(s) activé(s).')
    mark_as_active.short_description = 'Activer'
    
    def mark_as_inactive(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} produit(s) désactivé(s).')
    mark_as_inactive.short_description = 'Désactiver'
    
    def mark_as_featured(self, request, queryset):
        count = queryset.update(is_featured=True)
        self.message_user(request, f'{count} produit(s) mis en vedette.')
    mark_as_featured.short_description = 'Mettre en vedette'


@admin.register(Piece)
class PieceAdmin(admin.ModelAdmin):
    """Admin pour les pièces"""
    list_display = ['id', 'nom', 'reference', 'prix', 'stock', 'produit', 'created_at']
    list_filter = ['created_at']
    search_fields = ['nom', 'reference', 'description']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Informations', {
            'fields': ('nom', 'reference', 'prix', 'stock', 'produit')
        }),
        ('Détails', {
            'fields': ('description', 'compatibilite')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']


class LigneCommandeInline(admin.TabularInline):
    """Inline pour les lignes de commande"""
    model = LigneCommande
    extra = 0
    readonly_fields = ['prix_unitaire']
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Commande)
class CommandeAdmin(admin.ModelAdmin):
    """Admin pour les commandes"""
    list_display = [
        'id', 'get_client_name', 'date', 'status', 'payment_status',
        'prix_total', 'frais_livraison', 'get_nombre_articles'
    ]
    list_filter = ['status', 'payment_status', 'date']
    search_fields = [
        'id', 'client__user__username', 'client__user__email',
        'adresse_livraison', 'telephone_livraison'
    ]
    ordering = ['-date']
    date_hierarchy = 'date'
    list_per_page = 25
    
    fieldsets = (
        ('Client', {
            'fields': ('client',)
        }),
        ('Statut', {
            'fields': ('status', 'payment_status')
        }),
        ('Prix', {
            'fields': ('prix_total', 'frais_livraison')
        }),
        ('Livraison', {
            'fields': ('adresse_livraison', 'telephone_livraison')
        }),
        ('Notes', {
            'fields': ('notes', 'notes_admin'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('date', 'date_paiement', 'date_expedition', 'date_livraison', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['date', 'prix_total', 'updated_at']
    
    inlines = [LigneCommandeInline]
    
    actions = ['mark_as_processing', 'mark_as_shipped', 'mark_as_delivered']
    
    def get_client_name(self, obj):
        return obj.client.user.get_full_name() or obj.client.user.username
    get_client_name.short_description = 'Client'
    get_client_name.admin_order_field = 'client__user__username'
    
    def get_nombre_articles(self, obj):
        return obj.nombre_articles
    get_nombre_articles.short_description = 'Articles'
    
    def mark_as_processing(self, request, queryset):
        count = queryset.update(status='processing')
        self.message_user(request, f'{count} commande(s) en traitement.')
    mark_as_processing.short_description = 'Marquer en traitement'
    
    def mark_as_shipped(self, request, queryset):
        from django.utils import timezone
        count = 0
        for commande in queryset:
            commande.status = 'shipped'
            if not commande.date_expedition:
                commande.date_expedition = timezone.now()
            commande.save()
            count += 1
        self.message_user(request, f'{count} commande(s) expédiée(s).')
    mark_as_shipped.short_description = 'Marquer comme expédié'
    
    def mark_as_delivered(self, request, queryset):
        from django.utils import timezone
        count = 0
        for commande in queryset:
            commande.status = 'delivered'
            if not commande.date_livraison:
                commande.date_livraison = timezone.now()
            commande.save()
            count += 1
        self.message_user(request, f'{count} commande(s) livrée(s).')
    mark_as_delivered.short_description = 'Marquer comme livré'


@admin.register(Avis)
class AvisAdmin(admin.ModelAdmin):
    """Admin pour les avis"""
    list_display = [
        'id', 'get_produit_nom', 'get_client_name', 'note',
        'is_verified_purchase', 'created_at'
    ]
    list_filter = ['note', 'created_at']
    search_fields = [
        'produit__nom', 'client__user__username', 'commentaire'
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    list_per_page = 25
    
    fieldsets = (
        ('Avis', {
            'fields': ('produit', 'client', 'note', 'commentaire')
        }),
        ('Achat vérifié', {
            'fields': ('commande',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def get_produit_nom(self, obj):
        return obj.produit.nom
    get_produit_nom.short_description = 'Produit'
    get_produit_nom.admin_order_field = 'produit__nom'
    
    def get_client_name(self, obj):
        return obj.client.user.get_full_name() or obj.client.user.username
    get_client_name.short_description = 'Client'
    get_client_name.admin_order_field = 'client__user__username'
    
    def is_verified_purchase(self, obj):
        return obj.commande is not None
    is_verified_purchase.boolean = True
    is_verified_purchase.short_description = 'Achat vérifié'