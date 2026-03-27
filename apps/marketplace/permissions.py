from rest_framework import permissions


class IsVendorOrAdmin(permissions.BasePermission):
    """
    Permission: Vendeur ou administrateur
    """
    
    def has_permission(self, request, view):
        # Lecture pour tous les authentifiés
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        # Création/modification pour vendeurs et admins
        return (
            request.user and
            request.user.is_authenticated and
            request.user.user_type in ['vendor', 'administrator']
        )
    
    def has_object_permission(self, request, view, obj):
        # Lecture pour tous
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Admin peut tout faire
        if request.user.is_staff or request.user.user_type == 'administrator':
            return True
        
        # Vendeur ne peut modifier que ses produits
        if hasattr(obj, 'vendeur'):
            return obj.vendeur == request.user
        
        return False


class IsProductOwner(permissions.BasePermission):
    """
    Permission: Propriétaire du produit
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin a tous les droits
        if request.user.is_staff or request.user.user_type == 'administrator':
            return True
        
        # Vendeur propriétaire
        return obj.vendeur == request.user


class IsCommandeOwner(permissions.BasePermission):
    """
    Permission: Propriétaire de la commande ou admin
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin a tous les droits
        if request.user.is_staff or request.user.user_type == 'administrator':
            return True
        
        # Client propriétaire
        if hasattr(request.user, 'client_profile'):
            return obj.client == request.user.client_profile
        
        return False


class CanCreateCommande(permissions.BasePermission):
    """
    Permission: Seuls les clients peuvent créer des commandes
    """
    
    def has_permission(self, request, view):
        if request.method != 'POST':
            return True
        
        return (
            request.user and
            request.user.is_authenticated and
            request.user.user_type == 'client'
        )


class CanReview(permissions.BasePermission):
    """
    Permission: Seuls les clients peuvent laisser des avis
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.user_type == 'client'
        )
    
    def has_object_permission(self, request, view, obj):
        # Seul l'auteur peut modifier/supprimer son avis
        if request.method in ['PUT', 'PATCH', 'DELETE']:
            return obj.client.user == request.user
        
        return True