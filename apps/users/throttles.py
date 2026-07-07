from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    """Limite les tentatives de connexion et d'inscription."""
    scope = 'auth'


class RegisterRateThrottle(AnonRateThrottle):
    """Limite les créations de compte."""
    scope = 'register'
