from rest_framework import permissions


class IsReservationOwner(permissions.BasePermission):
    """Propriétaire de la réservation"""
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.user_type == 'administrator':
            return True
        
        if hasattr(request.user, 'client_profile') and obj.client == request.user.client_profile:
            return True
        
        if hasattr(request.user, 'technician_profile') and obj.technician == request.user.technician_profile:
            return True
        
        return False


class CanCreateReservation(permissions.BasePermission):
    """Seuls les clients peuvent créer"""
    
    def has_permission(self, request, view):
        if request.method != 'POST':
            return True
        
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.user_type == 'client'
        )


class CanUpdateReservationStatus(permissions.BasePermission):
    """Gérer les transitions"""
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if user.is_staff or user.user_type == 'administrator':
            return True
        
        if hasattr(user, 'client_profile') and obj.client == user.client_profile:
            return True
        
        if hasattr(user, 'technician_profile') and obj.technician == user.technician_profile:
            return True
        
        return False


class CanEvaluate(permissions.BasePermission):
    """Seul le client peut évaluer"""
    
    def has_object_permission(self, request, view, obj):
        if not hasattr(request.user, 'client_profile'):
            return False
        
        if obj.client != request.user.client_profile:
            return False
        
        if obj.status != 'completed':
            return False
        
        if hasattr(obj, 'evaluation'):
            return False
        
        return True