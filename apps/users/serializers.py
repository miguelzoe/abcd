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


def build_profile_photo_url(user, request=None):
    """URL stable pour photo de profil stockée en base de données.

    On préfère l'endpoint API plutôt que l'URL media afin que les photos
    persistent même sur Render sans Disk.
    """
    if not user:
        return None
    if getattr(user, 'profile_photo_data', None):
        path = f'/api/users/{user.pk}/profile_photo/'
        return request.build_absolute_uri(path) if request else path
    photo = getattr(user, 'profile_photo', None)
    if photo:
        try:
            return request.build_absolute_uri(photo.url) if request else photo.url
        except Exception:
            pass
    try:
        tech_photo = getattr(getattr(user, 'technician_profile', None), 'profile_photo', None)
        if tech_photo:
            return request.build_absolute_uri(tech_photo.url) if request else tech_photo.url
    except Exception:
        pass
    return None



# ==================== USER SERIALIZERS ====================

class UserSerializer(serializers.ModelSerializer):
    """Serializer de base pour les utilisateurs"""
    full_name = serializers.SerializerMethodField()
    profile_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'telephone', 'user_type',
            'address',  # ✅ si présent dans ton User
            'profile_photo', 'profile_photo_url',
            'location', 'is_available',
            'date_joined', 'last_login', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'profile_photo', 'date_joined', 'last_login', 'created_at', 'updated_at']

    def get_profile_photo_url(self, obj):
        return build_profile_photo_url(obj, self.context.get('request'))

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
        fields = ['first_name', 'last_name', 'email', 'telephone', 'address']

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




class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.CharField(required=False, allow_blank=True)
    identifier = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        value = (attrs.get('identifier') or attrs.get('email') or '').strip()
        if not value:
            raise serializers.ValidationError({'identifier': 'Ce champ est obligatoire.'})
        attrs['identifier'] = value
        attrs['email'] = value
        return attrs


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({'new_password': 'Les mots de passe ne correspondent pas'})
        return data


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
    file_url = serializers.SerializerMethodField()
    view_url = serializers.SerializerMethodField()
    mime_type = serializers.CharField(source='safe_content_type', read_only=True)
    filename = serializers.CharField(source='display_name', read_only=True)
    storage_mode = serializers.SerializerMethodField()

    class Meta:
        model = TechnicianDocument
        fields = [
            'id', 'name', 'filename', 'document_type', 'file', 'file_url', 'view_url',
            'mime_type', 'content_type', 'file_size', 'storage_mode',
            'validation_status', 'validation_comment', 'created_at',
        ]
        read_only_fields = [
            'id', 'filename', 'file_url', 'view_url', 'mime_type', 'content_type',
            'file_size', 'storage_mode', 'created_at',
        ]

    def _admin_document_url(self, obj):
        request = self.context.get('request')
        if not obj.pk or not obj.technician_id:
            return None
        path = f'/api/admin/users/{obj.technician.user_id}/documents/{obj.pk}/view/'
        return request.build_absolute_uri(path) if request else path

    def get_file_url(self, obj):
        # Retourne désormais une URL API protégée qui lit le document depuis PostgreSQL.
        return self._admin_document_url(obj)

    def get_view_url(self, obj):
        return self._admin_document_url(obj)

    def get_storage_mode(self, obj):
        return 'database' if obj.has_database_file else ('legacy_media' if obj.file else 'missing')


# ==================== TECHNICIAN SERIALIZERS ====================

class TechnicianSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    documents = TechnicianDocumentSerializer(many=True, read_only=True)
    distance = serializers.SerializerMethodField()
    profile_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Technician
        fields = [
            'id', 'user',
            'certifications', 'status', 'specializations',
            'rating', 'total_interventions', 'approval_status', 'rejection_reason',
            'years_experience', 'profile_photo', 'profile_photo_url', 'documents', 'distance'
        ]

    def get_profile_photo_url(self, obj):
        return build_profile_photo_url(obj.user, self.context.get('request'))

    def get_distance(self, obj):
        if hasattr(obj, 'distance'):
            return round(obj.distance.km, 2)
        return None


class TechnicianListSerializer(serializers.ModelSerializer):
    profile_photo_url = serializers.SerializerMethodField()
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    telephone = serializers.CharField(source='user.telephone', read_only=True)
    is_available = serializers.BooleanField(source='user.is_available', read_only=True)
    location = serializers.SerializerMethodField()

    class Meta:
        model = Technician
        fields = [
            'id', 'username', 'full_name', 'telephone', 'status',
            'specializations', 'rating', 'total_interventions', 'is_available',
            'approval_status', 'years_experience', 'profile_photo', 'profile_photo_url', 'location'
        ]

    def get_profile_photo_url(self, obj):
        return build_profile_photo_url(obj.user, self.context.get('request'))

    def get_location(self, obj):
        if obj.user.location:
            return {'latitude': obj.user.location.y, 'longitude': obj.user.location.x}
        return None


class TechnicianUpdateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name', required=False, allow_blank=True)
    last_name = serializers.CharField(source='user.last_name', required=False, allow_blank=True)
    telephone = serializers.CharField(source='user.telephone', required=False, allow_blank=True)
    address = serializers.CharField(source='user.address', required=False, allow_blank=True)

    class Meta:
        model = Technician
        fields = [
            'certifications', 'status', 'specializations',
            'years_experience', 'profile_photo',
            'first_name', 'last_name', 'telephone', 'address'
        ]

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        for attr, value in user_data.items():
            setattr(instance.user, attr, value)
        if user_data:
            instance.user.save()
        return super().update(instance, validated_data)




def infer_document_type_from_name(name: str) -> str:
    value = (name or '').lower()
    if any(key in value for key in ['cni', 'identit', 'passeport', 'passport']):
        return 'piece_identite'
    if any(key in value for key in ['certificat', 'dipl', 'formation']):
        return 'certificat'
    if any(key in value for key in ['experience', 'expérience', 'travail', 'recommandation']):
        return 'experience'
    if 'assurance' in value:
        return 'assurance'
    return 'autre'


def create_technician_document_from_upload(technician, uploaded_file):
    filename = getattr(uploaded_file, 'name', '') or 'document'
    content_type = getattr(uploaded_file, 'content_type', '') or 'application/octet-stream'
    data = uploaded_file.read()
    return TechnicianDocument.objects.create(
        technician=technician,
        name=filename,
        original_filename=filename,
        content_type=content_type,
        file_size=len(data),
        file_data=data,
        document_type=infer_document_type_from_name(filename),
        validation_status='non_verifie',
    )

# ==================== TECHNICIAN REGISTER SERIALIZER ====================

class TechnicianRegisterSerializer(serializers.Serializer):
    """
    Inscription technicien avec documents (multipart recommandé).

    Champs attendus :
    - user_type="technician"
    - username, email, password, password_confirm, first_name, last_name, telephone
    - address
    - specialties : "Mecanique, Electronique"
    - documents : multi fichiers (clé 'documents') - handled in create method
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
    specialties = serializers.CharField(required=False, allow_blank=True)
    specializations = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    years_experience = serializers.IntegerField(required=False, min_value=0, max_value=80, default=0)
    profile_photo = serializers.ImageField(required=False, allow_null=True)

    # ✅ accepte liste si DRF la parse, sinon on récupère depuis request.FILES
    documents = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        allow_empty=True
    )

    ALLOWED_DOCUMENT_TYPES = {'application/pdf', 'image/jpeg', 'image/png', 'image/webp'}
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
                    f"Le fichier '{f.name}' n'est pas autorisé. Types acceptés : PDF, JPEG, PNG, WEBP."
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
        specializations = validated_data.pop('specializations', [])
        address = validated_data.pop('address', '')
        years_experience = validated_data.pop('years_experience', 0)
        profile_photo = validated_data.pop('profile_photo', None)

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
        parsed_specialties = self._parse_specialties(specialties)
        if specializations:
            parsed_specialties = [str(s).strip() for s in specializations if str(s).strip()]
        tech.specializations = parsed_specialties
        tech.years_experience = years_experience or 0
        if profile_photo:
            try:
                data = profile_photo.read()
                profile_photo.seek(0)
                user.profile_photo_data = data
                user.profile_photo_content_type = getattr(profile_photo, 'content_type', '') or 'image/jpeg'
                user.profile_photo_filename = getattr(profile_photo, 'name', '') or 'profile.jpg'
                user.save(update_fields=['profile_photo_data', 'profile_photo_content_type', 'profile_photo_filename'])
            except Exception:
                pass
            tech.profile_photo = profile_photo
        tech.save(update_fields=['specializations', 'years_experience', 'profile_photo'])

        # ✅ créer documents directement en base de données
        docs = self.validate_documents(docs)
        for f in docs:
            create_technician_document_from_upload(tech, f)

        # ✅ notifier les administrateurs
        from apps.users.models import Administrator, Notification
        admins = Administrator.objects.all()
        for admin in admins:
            Notification.objects.create(
                user=admin.user,
                title="Nouvelle inscription technicien",
                body=f"Un nouveau technicien s'est inscrit : {tech.user.get_full_name() or tech.user.username}. Vérifiez ses documents et approuvez ou refusez sa demande.",
                data={'technician_id': tech.id, 'action': 'review_technician'}
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
        login_value = (attrs.get('username') or '').strip()
        if login_value:
            user = User.objects.filter(email__iexact=login_value).only('username').first()
            if not user:
                user = User.objects.filter(telephone=login_value).only('username').first()
            if not user:
                user = User.objects.filter(username__iexact=login_value).only('username').first()
            if user:
                attrs['username'] = user.username

        data = super().validate(attrs)
        
        # Vérifier l'accès pour les techniciens
        if self.user.user_type == 'technician':
            if not self.user.is_active:
                raise serializers.ValidationError({"detail": "Votre compte a été bloqué. Contactez le support."})
            if hasattr(self.user, 'technician_profile'):
                approval_status = self.user.technician_profile.approval_status
                if approval_status == 'pending':
                    raise serializers.ValidationError({"detail": "Votre inscription a bien été reçue. Elle est en attente de vérification par l’administrateur. Vous serez notifié dès validation."})
                elif approval_status == 'rejected':
                    reason = self.user.technician_profile.rejection_reason or "Veuillez contacter l’administration pour plus d’informations."
                    raise serializers.ValidationError({"detail": f"Votre inscription technicien n’a pas été validée. {reason}"})
        
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'address': self.user.address,
            'user_type': self.user.user_type,
            'telephone': self.user.telephone,
            'full_name': self.user.get_full_name(),
            'is_available': self.user.is_available,
            'profile_photo_url': build_profile_photo_url(self.user, self.context.get('request')),
        }
        return data


# ==================== PROFILE DETAIL SERIALIZER ====================

class UserProfileDetailSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    profile_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'telephone', 'user_type', 'address', 'profile_photo', 'profile_photo_url',
            'location', 'is_available', 'date_joined', 'last_login',
            'created_at', 'updated_at', 'profile'
        ]

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_profile_photo_url(self, obj):
        return build_profile_photo_url(obj, self.context.get('request'))

    def get_profile(self, obj):
        if obj.user_type == 'client' and hasattr(obj, 'client_profile'):
            return ClientSerializer(obj.client_profile, context=self.context).data
        elif obj.user_type == 'technician' and hasattr(obj, 'technician_profile'):
            return TechnicianSerializer(obj.technician_profile, context=self.context).data
        elif obj.user_type == 'vendor' and hasattr(obj, 'vendor_profile'):
            return VendorSerializer(obj.vendor_profile, context=self.context).data
        elif obj.user_type == 'administrator' and hasattr(obj, 'admin_profile'):
            return AdministratorSerializer(obj.admin_profile, context=self.context).data
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
