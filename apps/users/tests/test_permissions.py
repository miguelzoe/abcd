"""
Tests de permissions : chaque rôle n'accède qu'à ce qu'il est autorisé à voir.
"""
import pytest
from rest_framework import status

USERS_URL = "/api/users/"
CLIENTS_URL = "/api/clients/"
TECHNICIANS_URL = "/api/technicians/"
VENDORS_URL = "/api/vendors/"
ADMINS_URL = "/api/administrators/"


@pytest.mark.django_db
class TestUnauthenticatedAccess:
    """Un utilisateur non connecté ne peut accéder à rien."""

    def test_users_list_requires_auth(self, api_client):
        response = api_client.get(USERS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_clients_list_requires_auth(self, api_client):
        response = api_client.get(CLIENTS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_technicians_list_requires_auth(self, api_client):
        response = api_client.get(TECHNICIANS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestClientPermissions:
    """Un client ne voit que ses propres données."""

    def test_client_sees_only_own_profile(self, auth_client, client_user):
        response = auth_client.get(USERS_URL)
        assert response.status_code == status.HTTP_200_OK
        # Un client ne voit que lui-même
        for user in response.data.get("results", response.data):
            assert user["id"] == client_user.id

    def test_client_cannot_access_admin_endpoint(self, auth_client):
        response = auth_client.get(ADMINS_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_client_cannot_delete_users(self, auth_client, technician_user):
        response = auth_client.delete(f"{USERS_URL}{technician_user.id}/")
        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )

    def test_client_can_update_own_profile(self, auth_client, client_user):
        response = auth_client.patch(f"{USERS_URL}{client_user.id}/", {
            "first_name": "NouveauPrenom",
        }, format="json")
        assert response.status_code == status.HTTP_200_OK

    def test_client_cannot_update_other_user(self, auth_client, technician_user):
        response = auth_client.patch(f"{USERS_URL}{technician_user.id}/", {
            "first_name": "Hacked",
        }, format="json")
        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )


@pytest.mark.django_db
class TestTechnicianPermissions:
    """Un technicien peut consulter les technicians mais pas administrer."""

    def test_technician_can_list_technicians(self, auth_technician):
        response = auth_technician.get(TECHNICIANS_URL)
        assert response.status_code == status.HTTP_200_OK

    def test_technician_cannot_access_admin_endpoint(self, auth_technician):
        response = auth_technician.get(ADMINS_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_technician_can_update_own_status(self, auth_technician, technician_user):
        tech = technician_user.technician_profile
        response = auth_technician.patch(
            f"{TECHNICIANS_URL}{tech.id}/update_status/",
            {"status": "busy"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        tech.refresh_from_db()
        assert tech.status == "busy"

    def test_technician_cannot_update_other_technician_status(
        self, auth_technician, db
    ):
        from conftest import make_user
        other_tech_user = make_user("other_tech", "technician", "+237600009999")
        other_tech = other_tech_user.technician_profile

        response = auth_technician.patch(
            f"{TECHNICIANS_URL}{other_tech.id}/update_status/",
            {"status": "busy"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAdminPermissions:
    """Un administrateur a accès à tout."""

    def test_admin_can_list_all_users(self, auth_admin):
        response = auth_admin.get(USERS_URL)
        assert response.status_code == status.HTTP_200_OK

    def test_admin_can_access_admin_endpoint(self, auth_admin):
        response = auth_admin.get(ADMINS_URL)
        assert response.status_code == status.HTTP_200_OK

    def test_admin_can_verify_vendor(self, auth_admin, vendor_user):
        vendor = vendor_user.vendor_profile
        response = auth_admin.post(f"{VENDORS_URL}{vendor.id}/verify/")
        assert response.status_code == status.HTTP_200_OK
        vendor.refresh_from_db()
        assert vendor.is_verified is True

    def test_admin_dashboard_stats(self, auth_admin):
        response = auth_admin.get("/api/administrators/dashboard_stats/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert "users" in data
        assert "reservations" in data
        assert "marketplace" in data
