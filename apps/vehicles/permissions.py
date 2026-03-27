from rest_framework import permissions


class IsVehicleOwner(permissions.BasePermission):
    """
    Permission: Propriétaire du véhicule ou administrateur
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin a tous les droits
        if request.user.is_staff or request.user.user_type == 'administrator':
            return True
        
        # Vérifier si l'utilisateur est propriétaire du véhicule
        if request.user.user_type == 'client':
            return obj.proprietaires.filter(user=request.user).exists()
        
        return False


class CanCreateVehicle(permissions.BasePermission):
    """
    Permission: Seuls les clients peuvent créer des véhicules
    """
    
    def has_permission(self, request, view):
        if request.method != 'POST':
            return True
        
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.user_type == 'client'
        )


class CanManageMaintenance(permissions.BasePermission):
    """
    Permission: Gérer les maintenances
    """
    
    def has_permission(self, request, view):
        # Admin et techniciens peuvent voir toutes les maintenances
        if request.user.is_staff or request.user.user_type in ['administrator', 'technician']:
            return True
        
        # Clients peuvent voir les maintenances de leurs véhicules
        if request.user.user_type == 'client':
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        # Admin a tous les droits
        if request.user.is_staff or request.user.user_type == 'administrator':
            return True
        
        # Technicien peut voir les maintenances qu'il a effectuées
        if request.user.user_type == 'technician':
            if hasattr(request.user, 'technician_profile'):
                return obj.technician == request.user.technician_profile
        
        # Client peut voir les maintenances de ses véhicules
        if request.user.user_type == 'client':
            return obj.vehicle.proprietaires.filter(user=request.user).exists()
        
        return False