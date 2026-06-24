import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point

User = get_user_model()


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_user(username, user_type, telephone, **kwargs):
    """Crée un utilisateur et son profil associé."""
    from apps.users.models import Client, Technician, Vendor, Administrator

    user = User.objects.create_user(
        username=username,
        email=f"{username}@test.com",
        password="TestPass123!",
        user_type=user_type,
        telephone=telephone,
        first_name="Test",
        last_name=username.capitalize(),
        **kwargs,
    )

    profile_map = {
        "client": lambda: Client.objects.get_or_create(user=user),
        "technician": lambda: Technician.objects.get_or_create(user=user),
        "vendor": lambda: Vendor.objects.get_or_create(user=user),
        "administrator": lambda: Administrator.objects.get_or_create(user=user),
    }
    if user_type in profile_map:
        profile_map[user_type]()

    return user


# ─── Fixtures utilisateurs ───────────────────────────────────────────────────

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def client_user(db):
    return make_user("client_test", "client", "+237600000001")


@pytest.fixture
def technician_user(db):
    return make_user("tech_test", "technician", "+237600000002")


@pytest.fixture
def vendor_user(db):
    return make_user("vendor_test", "vendor", "+237600000003")


@pytest.fixture
def admin_user(db):
    user = make_user("admin_test", "administrator", "+237600000004")
    user.is_staff = True
    user.save()
    return user


# ─── Fixtures API avec auth ──────────────────────────────────────────────────

@pytest.fixture
def auth_client(api_client, client_user):
    api_client.force_authenticate(user=client_user)
    return api_client


@pytest.fixture
def auth_technician(api_client, technician_user):
    api_client.force_authenticate(user=technician_user)
    return api_client


@pytest.fixture
def auth_vendor(api_client, vendor_user):
    api_client.force_authenticate(user=vendor_user)
    return api_client


@pytest.fixture
def auth_admin(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


# ─── Fixture produit marketplace ─────────────────────────────────────────────

@pytest.fixture
def produit(db, vendor_user):
    from apps.marketplace.models import Produit
    return Produit.objects.create(
        nom="Filtre à huile",
        description="Filtre compatible Toyota",
        prix=5000,
        stock=10,
        category="part",
        vendeur=vendor_user,
    )


# ─── Fixture client profile ──────────────────────────────────────────────────

@pytest.fixture
def client_profile(client_user):
    return client_user.client_profile
