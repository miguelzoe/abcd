"""
Tests d'authentification : inscription, connexion, JWT, changement de mot de passe.
"""
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status

User = get_user_model()

REGISTER_URL = "/api/users/register/"
LOGIN_URL = "/api/token/"
REFRESH_URL = "/api/token/refresh/"
CHANGE_PWD_URL = "/api/users/change_password/"
ME_URL = "/api/users/me/"


# ─── Inscription CLIENT ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestClientRegistration:

    def test_register_client_success(self, api_client):
        payload = {
            "username": "nouveau_client",
            "email": "client@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "first_name": "Jean",
            "last_name": "Dupont",
            "telephone": "+237677000001",
            "user_type": "client",
        }
        response = api_client.post(REGISTER_URL, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.filter(username="nouveau_client").exists()
        user = User.objects.get(username="nouveau_client")
        assert user.user_type == "client"
        assert hasattr(user, "client_profile")

    def test_register_duplicate_email(self, api_client, client_user):
        payload = {
            "username": "autre_user",
            "email": client_user.email,  # email déjà pris
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "first_name": "Jean",
            "last_name": "Dupont",
            "telephone": "+237677000099",
            "user_type": "client",
        }
        response = api_client.post(REGISTER_URL, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_password_mismatch(self, api_client):
        payload = {
            "username": "client_mismatch",
            "email": "mismatch@example.com",
            "password": "SecurePass123!",
            "password_confirm": "DifferentPass!",
            "first_name": "Jean",
            "last_name": "Dupont",
            "telephone": "+237677000002",
            "user_type": "client",
        }
        response = api_client.post(REGISTER_URL, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_short_password(self, api_client):
        payload = {
            "username": "client_short",
            "email": "short@example.com",
            "password": "abc",
            "password_confirm": "abc",
            "first_name": "Jean",
            "last_name": "Dupont",
            "telephone": "+237677000003",
            "user_type": "client",
        }
        response = api_client.post(REGISTER_URL, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_invalid_phone(self, api_client):
        """Le téléphone doit commencer par +"""
        payload = {
            "username": "client_badphone",
            "email": "badphone@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "first_name": "Jean",
            "last_name": "Dupont",
            "telephone": "677000001",  # pas de +
            "user_type": "client",
        }
        response = api_client.post(REGISTER_URL, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_vendor_not_allowed(self, api_client):
        """L'inscription vendor via /register/ doit être refusée"""
        payload = {
            "username": "vendor_bad",
            "email": "vendor@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "first_name": "Jean",
            "last_name": "Dupont",
            "telephone": "+237677000010",
            "user_type": "vendor",
        }
        response = api_client.post(REGISTER_URL, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_without_user_type(self, api_client):
        payload = {
            "username": "notype",
            "email": "notype@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "first_name": "Jean",
            "last_name": "Dupont",
            "telephone": "+237677000011",
        }
        response = api_client.post(REGISTER_URL, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_password_not_in_response(self, api_client):
        """Le mot de passe ne doit jamais apparaître dans la réponse"""
        payload = {
            "username": "secure_check",
            "email": "secure@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "first_name": "Test",
            "last_name": "User",
            "telephone": "+237677000020",
            "user_type": "client",
        }
        response = api_client.post(REGISTER_URL, payload, format="json")

        assert "password" not in response.data
        assert "password_confirm" not in response.data


# ─── Connexion / JWT ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLogin:

    def test_login_success(self, api_client, client_user):
        response = api_client.post(LOGIN_URL, {
            "username": client_user.username,
            "password": "TestPass123!",
        }, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        assert "user" in response.data
        assert response.data["user"]["user_type"] == "client"

    def test_login_wrong_password(self, api_client, client_user):
        response = api_client.post(LOGIN_URL, {
            "username": client_user.username,
            "password": "WrongPassword!",
        }, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_unknown_user(self, api_client):
        response = api_client.post(LOGIN_URL, {
            "username": "fantome",
            "password": "TestPass123!",
        }, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_refresh(self, api_client, client_user):
        login = api_client.post(LOGIN_URL, {
            "username": client_user.username,
            "password": "TestPass123!",
        }, format="json")
        refresh_token = login.data["refresh"]

        response = api_client.post(REFRESH_URL, {"refresh": refresh_token}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    def test_access_protected_endpoint_without_token(self, api_client):
        response = api_client.get(ME_URL)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_access_protected_endpoint_with_token(self, api_client, client_user):
        login = api_client.post(LOGIN_URL, {
            "username": client_user.username,
            "password": "TestPass123!",
        }, format="json")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        response = api_client.get(ME_URL)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["username"] == client_user.username


# ─── Changement de mot de passe ───────────────────────────────────────────────

@pytest.mark.django_db
class TestChangePassword:

    def test_change_password_success(self, auth_client):
        response = auth_client.post(CHANGE_PWD_URL, {
            "old_password": "TestPass123!",
            "new_password": "NewSecure456!",
            "new_password_confirm": "NewSecure456!",
        }, format="json")

        assert response.status_code == status.HTTP_200_OK

    def test_change_password_wrong_old(self, auth_client):
        response = auth_client.post(CHANGE_PWD_URL, {
            "old_password": "WrongOldPass!",
            "new_password": "NewSecure456!",
            "new_password_confirm": "NewSecure456!",
        }, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_change_password_mismatch(self, auth_client):
        response = auth_client.post(CHANGE_PWD_URL, {
            "old_password": "TestPass123!",
            "new_password": "NewSecure456!",
            "new_password_confirm": "DifferentNew!",
        }, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_change_password_requires_auth(self, api_client):
        response = api_client.post(CHANGE_PWD_URL, {
            "old_password": "TestPass123!",
            "new_password": "NewSecure456!",
            "new_password_confirm": "NewSecure456!",
        }, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ─── Format d'erreur unifié ──────────────────────────────────────────────────

@pytest.mark.django_db
class TestErrorFormat:

    def test_error_response_has_unified_format(self, api_client):
        """Toutes les erreurs doivent suivre le format {error, message, details}"""
        response = api_client.post(LOGIN_URL, {
            "username": "inconnu",
            "password": "mauvais",
        }, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.data
        assert "message" in response.data
        assert response.data["error"] is True
