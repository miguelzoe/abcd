from rest_framework.permissions import BasePermission


class IsAdministrator(BasePermission):
    """Accès réservé aux administrateurs"""
    message = "Seuls les administrateurs peuvent accéder à cette ressource."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and (
                request.user.user_type == 'administrator'
                or request.user.is_staff
                or request.user.is_superuser
            )
        )