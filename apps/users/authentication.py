"""
apps/users/authentication.py
============================
Authentification JWT hybride : header Authorization Bearer (rétrocompat mobile)
puis fallback sur le cookie HttpOnly `access_token` (clients navigateur).
"""
from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """
    Ordre de lecture :
    1. Header  →  Authorization: Bearer <token>
    2. Cookie  →  access_token=<token>  (HttpOnly, posé par CookieTokenObtainPairView)
    """

    def authenticate(self, request):
        # 1. Essayer le header standard (clients mobiles / Postman / scripts)
        header = self.get_header(request)
        if header is not None:
            raw_token = self.get_raw_token(header)
            if raw_token is None:
                return None
        else:
            # 2. Fallback : cookie HttpOnly
            cookie_token = request.COOKIES.get('access_token')
            if cookie_token is None:
                return None
            raw_token = cookie_token.encode('utf-8')

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token
