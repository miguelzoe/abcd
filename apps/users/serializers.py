from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.users.models import (
    Client,
    Technician,
    Vendor,
    Administrator,
    TechnicianDocument,
    PushToken,
    Notification,
)

User = get_user_model()


# ==================== USER SERIALIZERS ====================

class UserSerializer(serializers.ModelSerializer):
    """Serializer de base pour les utilisateurs"""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'telephone', 'user_type',
            'address',  # ✅ si présent dans ton User
            'location', 'is_available',
            'date_joined', 'last_login', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'created_at', 'updated_at']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer pour l'inscription CLIENT uniquement
    (ton view route déjà sur user_type == "client")
    """
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'telephone', 'user_type'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
        }

    def validate_telephone(self, value):
        if not value.startswith('+'):
            raise serializers.ValidationError("Le numéro doit commencer par + (ex: +237677123456)")
        if len(value) < 10:
            raise serializers.ValidationError("Numéro de téléphone trop court")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Cet email est déjà utilisé")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Ce nom d'utilisateur est déjà pris")
        return value

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({"password": "Les mots de passe ne correspondent pas"})

        # ✅ on force client ici (sécurité)
        if (data.get('user_type') or '').strip().lower() != 'client':
            raise serializers.ValidationError({"user_type": "Cette inscription est réservée aux clients (user_type=client)."})

        return data

    def create(self, validated_data):
        validated_data.pop('password_confirm', None)
        password = validated_data.pop('password')

        # ✅ sécurité : forcer user_type
        validated_data['user_type'] = 'client'

        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'telephone']

    def validate_email(self, value):
        user = self.context['request'].user
        if User.objects.exclude(pk=user.pk).filter(email=value).exists():
            raise serializers.ValidationError("Cet email est déjà utilisé")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "Les nouveaux mots de passe ne correspondent pas"})
        return data

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Mot de passe actuel incorrect")
        return value


class UpdateLocationSerializer(serializers.Serializer):
    latitude = serializers.FloatField(required=True, min_value=-90, max_value=90)
    longitude = serializers.FloatField(required=True, min_value=-180, max_value=180)


# ==================== CLIENT SERIALIZERS ====================

class ClientSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    total_reservations = serializers.SerializerMethodField()
    total_commandes = serializers.SerializerMethodField()
    total_vehicules = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = ['id', 'user', 'historique_commandes', 'total_reservations', 'total_commandes', 'total_vehicules']

    def get_total_reservations(self, obj):
        return obj.reservations.count() if hasattr(obj, 'reservations') else 0

    def get_total_commandes(self, obj):
        return obj.commandes.count() if hasattr(obj, 'commandes') else 0

    def get_total_vehicules(self, obj):
        return obj.vehicules.count() if hasattr(obj, 'vehicules') else 0


# ==================== TECHNICIAN DOCUMENT SERIALIZER ====================

class TechnicianDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TechnicianDocument
        fields = ['id', 'name', 'file', 'created_at']


# ==================== TECHNICIAN SERIALIZERS ====================

class TechnicianSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    documents = TechnicianDocumentSerializer(many=True, read_only=True)
    distance = serializers.SerializerMethodField()

    class Meta:
        model = Technician
        fields = [
            'id', 'user',
            'certifications', 'status', 'specializations',
            'rating', 'total_interventions',
            'documents', 'distance'
        ]

    def get_distance(self, obj):
        if hasattr(obj, 'distance'):
            return round(obj.distance.km, 2)
        return None


class TechnicianListSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    telephone = serializers.CharField(source='user.telephone', read_only=True)
    is_available = serializers.BooleanField(source='user.is_available', read_only=True)
    location = serializers.SerializerMethodField()

    class Meta:
        model = Technician
        fields = [
            'id', 'username', 'full_name', 'telephone', 'status',
            'specializations', 'rating', 'total_interventions', 'is_available', 'location'
        ]

    def get_location(self, obj):
        if obj.user.location:
            return {'latitude': obj.user.location.y, 'longitude': obj.user.location.x}
        return None


class TechnicianUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Technician
        fields = ['certifications', 'status', 'specializations']


# ==================== TECHNICIAN REGISTER SERIALIZER ====================

class TechnicianRegisterSerializer(serializers.Serializer):
    """
    Inscription technicien avec documents (multipart recommandé).

    Champs attendus :
    - user_type="technician"
    - username, email, password, password_confirm, first_name, last_name, telephone
    - address
    - specialties : "Mecanique, Electronique"
    - documents : multi fichiers (clé 'documents')
    """
    user_type = serializers.CharField()
    username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    first_name = serializers.CharField()
    last_name = serializers.CharField()
    telephone = serializers.CharField()

    address = serializers.CharField(required=False, allow_blank=True)
    specialties = serializers.CharField(required=True)

    # ✅ accepte liste si DRF la parse, sinon on récupère depuis request.FILES
    documents = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        allow_empty=True
    )

    ALLOWED_DOCUMENT_TYPES = {'application/pdf', 'image/jpeg', 'image/png'}
    MAX_DOCUMENT_SIZE_MB = 5

    def validate_documents(self, files):
        max_bytes = self.MAX_DOCUMENT_SIZE_MB * 1024 * 1024
        for f in files:
            if f.size > max_bytes:
                raise serializers.ValidationError(
                    f"Le fichier '{f.name}' dépasse la taille maximale de {self.MAX_DOCUMENT_SIZE_MB} Mo."
                )
            content_type = getattr(f, 'content_type', '')
            if content_type not in self.ALLOWED_DOCUMENT_TYPES:
                raise serializers.ValidationError(
                    f"Le fichier '{f.name}' n'est pas autorisé. Types acceptés : PDF, JPEG, PNG."
                )
        return files

    def validate_telephone(self, value):
        if not value.startswith('+'):
            raise serializers.ValidationError("Le numéro doit commencer par + (ex: +237677123456)")
        if len(value) < 10:
            raise serializers.ValidationError("Numéro de téléphone trop court")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Cet email est déjà utilisé")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Ce nom d'utilisateur est déjà pris")
        return value

    def validate_specialties(self, value):
        from apps.users.models import Technician
        if not value or not value.strip():
            raise serializers.ValidationError("Veuillez indiquer au moins une spécialité.")
        # Chaque spécialité doit être dans la liste officielle OU être une valeur libre (cas "Autre")
        items = [s.strip() for s in value.split(',') if s.strip()]
        allowed = set(Technician.SPECIALIZATION_CHOICES)
        for item in items:
            if item not in allowed and len(item) < 3:
                raise serializers.ValidationError(
                    f"Spécialité invalide : '{item}'. Veuillez saisir au moins 3 caractères."
                )
        return value

    def validate(self, data):
        if (data.get('user_type') or '').strip().lower() != 'technician':
            raise serializers.ValidationError({"user_type": "user_type doit être 'technician'."})

        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({"password": "Les mots de passe ne correspondent pas"})
        return data

    def _parse_specialties(self, raw):
        if not raw:
            return []
        return [s.strip() for s in str(raw).split(',') if s.strip()]

    def _get_documents_from_request(self):
        """
        Robustesse multipart: si DRF ne remplit pas 'documents' proprement,
        on récupère la liste dans request.FILES.getlist('documents').
        """
        request = self.context.get('request')
        if not request:
            return []
        return request.FILES.getlist('documents')

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop('password_confirm', None)
        password = validated_data.pop('password')

        specialties = validated_data.pop('specialties', '')
        address = validated_data.pop('address', '')

        docs = validated_data.pop('documents', None)
        if docs is None:
            docs = []
        # ✅ fallback multipart
        if not docs:
            docs = self._get_documents_from_request()

        # ✅ créer user (user_type forcé)
        user = User(
            user_type='technician',
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            telephone=validated_data['telephone'],
            address=address,
        )
        user.set_password(password)
        user.save()

        # ✅ évite doublon si signal post_save existe
        tech, _ = Technician.objects.get_or_create(user=user)
        tech.specializations = self._parse_specialties(specialties)
        tech.save(update_fields=['specializations'])

        # ✅ créer documents
        for f in docs:
            TechnicianDocument.objects.create(
                technician=tech,
                file=f,
                name=getattr(f, 'name', '') or ''
            )

        return tech


# ==================== VENDOR SERIALIZERS ====================

class VendorSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    total_produits = serializers.SerializerMethodField()

    class Meta:
        model = Vendor
        fields = [
            'id', 'user', 'company_name', 'business_license',
            'rating', 'total_sales', 'is_verified', 'total_produits'
        ]

    def get_total_produits(self, obj):
        return obj.user.produits.count() if hasattr(obj.user, 'produits') else 0


class VendorUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ['company_name', 'business_license']


# ==================== ADMINISTRATOR SERIALIZERS ====================

class AdministratorSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Administrator
        fields = ['id', 'user', 'permissions', 'department']


# ==================== JWT CUSTOM SERIALIZERS ====================

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['email'] = user.email
        token['user_type'] = user.user_type
        token['telephone'] = user.telephone
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'user_type': self.user.user_type,
            'telephone': self.user.telephone,
            'full_name': self.user.get_full_name(),
            'is_available': self.user.is_available,
        }
        return data


# ==================== PROFILE DETAIL SERIALIZER ====================

class UserProfileDetailSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'telephone', 'user_type', 'address', 'location', 'is_available',
            'date_joined', 'last_login', 'profile'
        ]

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_profile(self, obj):
        if obj.user_type == 'client' and hasattr(obj, 'client_profile'):
            return ClientSerializer(obj.client_profile).data
        elif obj.user_type == 'technician' and hasattr(obj, 'technician_profile'):
            return TechnicianSerializer(obj.technician_profile).data
        elif obj.user_type == 'vendor' and hasattr(obj, 'vendor_profile'):
            return VendorSerializer(obj.vendor_profile).data
        elif obj.user_type == 'administrator' and hasattr(obj, 'admin_profile'):
            return AdministratorSerializer(obj.admin_profile).data
        return None


# ==================== PUSH / NOTIFICATIONS ====================


class PushTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushToken
        fields = ['token', 'platform']


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'title', 'body', 'data', 'created_at', 'read_at', 'is_read']

    def get_is_read(self, obj):
        return obj.read_at is not None
