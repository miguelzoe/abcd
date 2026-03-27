from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission: Propriétaire de l'objet ou administrateur
    """
    
    def has_object_permission(self, request, view, obj):
        # Admins ont tous les droits
        if request.user.is_staff or request.user.user_type == 'administrator':
            return True
        
        # Vérifier si l'objet a un attribut 'user'
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Sinon, vérifier si l'objet est l'utilisateur lui-même
        return obj == request.user


class IsClient(permissions.BasePermission):
    """
    Permission: Utilisateur de type client
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.user_type == 'client'
        )


class IsTechnician(permissions.BasePermission):
    """
    Permission: Utilisateur de type technicien
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.user_type == 'technician'
        )


class IsVendor(permissions.BasePermission):
    """
    Permission: Utilisateur de type vendeur
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.user_type == 'vendor'
        )


class IsAdministrator(permissions.BasePermission):
    """
    Permission: Utilisateur de type administrateur
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            (request.user.user_type == 'administrator' or request.user.is_staff)
        )


class IsOwner(permissions.BasePermission):
    """
    Permission: Propriétaire uniquement
    """
    
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return obj == request.user


class ReadOnly(permissions.BasePermission):
    """
    Permission: Lecture seule pour tout le monde
    """
    
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS