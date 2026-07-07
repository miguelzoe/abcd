from rest_framework import serializers
from django.utils import timezone

from apps.admin_panel.models import Signalement, Notification
from apps.users.models import User, Client, Technician, Vendor, Administrator
from apps.users.serializers import UserSerializer
from apps.reservations.models import Reservation, Invoice
from apps.marketplace.models import Commande


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

class DashboardStatsSerializer(serializers.Serializer):
    """Stats synthétiques pour le dashboard admin"""
    utilisateursTotaux = serializers.IntegerField()
    utilisateursVariation = serializers.FloatField()  # % vs mois dernier
    signalementEnAttente = serializers.IntegerField()
    revenusMois = serializers.FloatField()
    revenusVariation = serializers.FloatField()


class UserEvolutionSerializer(serializers.Serializer):
    mois = serializers.CharField()
    clients = serializers.IntegerField()
    techniciens = serializers.IntegerField()


# ─────────────────────────────────────────────────────────────────────────────
# USERS (Admin view)
# ─────────────────────────────────────────────────────────────────────────────

class DocumentJustificatifSerializer(serializers.Serializer):
    """Sérialise les TechnicianDocument en format attendu par le frontend admin."""
    id = serializers.CharField(source='pk')
    type = serializers.SerializerMethodField()
    label = serializers.SerializerMethodField()
    fichier = serializers.SerializerMethodField()
    viewUrl = serializers.SerializerMethodField()
    mimeType = serializers.SerializerMethodField()
    fileSize = serializers.IntegerField(source='file_size')
    storageMode = serializers.SerializerMethodField()
    dateDepot = serializers.DateTimeField(source='created_at')
    status = serializers.SerializerMethodField()
    commentaire = serializers.SerializerMethodField()

    def get_type(self, obj):
        doc_type = getattr(obj, 'document_type', '') or ''
        if doc_type in {'piece_identite', 'certificat', 'experience', 'assurance', 'autre'}:
            return 'certificat' if doc_type == 'experience' else doc_type

        name_lower = (obj.display_name or '').lower()
        if 'identit' in name_lower or 'cni' in name_lower or 'passeport' in name_lower:
            return 'piece_identite'
        if 'diplome' in name_lower or 'diplôme' in name_lower or 'bts' in name_lower or 'cap' in name_lower:
            return 'diplome'
        if 'certificat' in name_lower or 'experience' in name_lower or 'expérience' in name_lower:
            return 'certificat'
        if 'assurance' in name_lower:
            return 'assurance'
        return 'autre'

    def get_label(self, obj):
        return obj.display_name

    def _view_url(self, obj):
        request = self.context.get('request')
        path = f'/api/admin/users/{obj.technician.user_id}/documents/{obj.pk}/view/'
        return request.build_absolute_uri(path) if request else path

    def get_fichier(self, obj):
        # URL API protégée : le contenu est lu depuis PostgreSQL, pas depuis /media.
        return self._view_url(obj)

    def get_viewUrl(self, obj):
        return self._view_url(obj)

    def get_mimeType(self, obj):
        return obj.safe_content_type

    def get_storageMode(self, obj):
        return 'database' if obj.has_database_file else ('legacy_media' if obj.file else 'missing')

    def get_status(self, obj):
        return getattr(obj, 'validation_status', 'non_verifie')

    def get_commentaire(self, obj):
        return getattr(obj, 'validation_comment', None)


class TechnicienProfileSerializer(serializers.Serializer):
    specialites = serializers.ListField(child=serializers.CharField())
    anneesExperience = serializers.IntegerField(default=0)
    ville = serializers.CharField()
    documents = serializers.SerializerMethodField()
    motifRefus = serializers.CharField(allow_null=True, required=False)

    def get_documents(self, obj):
        docs = obj.documents.all()
        return DocumentJustificatifSerializer(
            docs, many=True, context=self.context
        ).data


class AdminUserListSerializer(serializers.ModelSerializer):
    """Sérialise les utilisateurs pour la liste admin (correspond au modèle User Angular)"""
    id = serializers.CharField(source='pk')
    nom = serializers.CharField(source='last_name')
    prenom = serializers.CharField(source='first_name')
    role = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    telephone = serializers.CharField()
    createdAt = serializers.DateTimeField(source='created_at')
    updatedAt = serializers.DateTimeField(source='updated_at')
    technicienProfile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'nom', 'prenom', 'email', 'role', 'status',
            'telephone', 'createdAt', 'updatedAt', 'technicienProfile',
        ]

    def get_role(self, obj):
        mapping = {
            'client': 'client',
            'technician': 'technicien',
            'vendor': 'vendeur',
            'administrator': 'administrateur',
        }
        return mapping.get(obj.user_type, obj.user_type)

    def get_status(self, obj):
        """
        Logique de statut :
        - Technicien → utilise approval_status (en_attente, approuvé, refusé)
        - Tout autre utilisateur avec is_active=False → 'bloque'
        - is_active=True → 'actif'
        """
        if obj.user_type == 'technician':
            try:
                tech = obj.technician_profile
                status_mapping = {
                    'pending': 'en_attente',
                    'approved': 'actif',
                    'rejected': 'refuse',
                }
                return status_mapping.get(tech.approval_status, 'en_attente')
            except Exception:
                return 'en_attente'
        
        # Pour les autres utilisateurs
        if not obj.is_active:
            return 'bloque'
        return 'actif'

    def get_technicienProfile(self, obj):
        if obj.user_type != 'technician':
            return None
        try:
            tech = obj.technician_profile
            address_parts = obj.address.split(',')
            ville = address_parts[-1].strip() if address_parts else obj.address

            profile_data = {
                'specialites': tech.specializations or [],
                'anneesExperience': getattr(tech, 'years_experience', 0),
                'ville': ville,
            }

            docs = tech.documents.all()
            serialized_docs = DocumentJustificatifSerializer(
                docs, many=True, context=self.context
            ).data
            profile_data['documents'] = serialized_docs
            
            # Ajouter le motif de refus si le technicien a été refusé
            if tech.approval_status == 'rejected' and tech.rejection_reason:
                profile_data['motifRefus'] = tech.rejection_reason

            return profile_data
        except Exception:
            return None


class AdminUserDetailSerializer(AdminUserListSerializer):
    """Détail complet d'un utilisateur pour l'admin"""
    username = serializers.CharField()
    isActive = serializers.BooleanField(source='is_active')
    isStaff = serializers.BooleanField(source='is_staff')

    class Meta(AdminUserListSerializer.Meta):
        fields = AdminUserListSerializer.Meta.fields + ['username', 'isActive', 'isStaff']


# ─────────────────────────────────────────────────────────────────────────────
# SIGNALEMENTS (Modération)
# ─────────────────────────────────────────────────────────────────────────────

class SignalementSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)
    signalePar = serializers.SerializerMethodField()
    note = serializers.CharField(source='note_admin', allow_blank=True, required=False)
    nombreFoisSignale = serializers.IntegerField(source='nombre_fois_signale')
    date = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = Signalement
        fields = [
            'id', 'contenu', 'signalePar', 'raison', 'type',
            'status', 'date', 'note', 'nombreFoisSignale',
        ]

    def get_signalePar(self, obj):
        if obj.signale_par:
            return obj.signale_par.get_full_name() or obj.signale_par.username
        return obj.signale_par_nom or 'Anonyme'


class SignalementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Signalement
        fields = ['contenu', 'raison', 'type', 'utilisateur_vise', 'nombre_fois_signale']

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['signale_par'] = request.user
            validated_data['signale_par_nom'] = request.user.get_full_name() or request.user.username
        return super().create(validated_data)


class SignalementTraiterSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True)


# ─────────────────────────────────────────────────────────────────────────────
# INTERVENTIONS (Réservations vue admin)
# ─────────────────────────────────────────────────────────────────────────────

class AdminInterventionSerializer(serializers.ModelSerializer):
    """Sérialise les Reservation en format Intervention pour le frontend admin"""
    id = serializers.CharField(read_only=True)
    titre = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    client = serializers.SerializerMethodField()
    technicien = serializers.SerializerMethodField()
    vehicule = serializers.SerializerMethodField()
    date = serializers.DateTimeField()
    montant = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    adresse = serializers.CharField(source='location_description')
    description = serializers.CharField(allow_blank=True, required=False)

    class Meta:
        model = Reservation
        fields = [
            'id', 'titre', 'type', 'client', 'technicien',
            'vehicule', 'date', 'montant', 'status', 'adresse', 'description',
        ]

    def get_titre(self, obj):
        return obj.description[:60] if obj.description else obj.get_service_type_display()

    def get_type(self, obj):
        mapping = {
            'emergency': 'diagnostic',
            'diagnosis': 'diagnostic',
            'roadside_repair': 'autre',
            'towing': 'autre',
            'scheduled_maintenance': 'revision',
            'specific_repair': 'autre',
            'preventive_maintenance': 'revision',
        }
        return mapping.get(obj.service_type, 'autre')

    def get_client(self, obj):
        user = obj.client.user
        return {
            'nom': user.last_name or user.username,
            'prenom': user.first_name,
            'email': user.email,
        }

    def get_technicien(self, obj):
        if not obj.technician:
            return {'nom': 'Non assigné', 'prenom': ''}
        user = obj.technician.user
        return {
            'nom': user.last_name or user.username,
            'prenom': user.first_name,
        }

    def get_vehicule(self, obj):
        if obj.vehicle:
            return f"{obj.vehicle.brand} {obj.vehicle.model} {obj.vehicle.year}"
        return 'Véhicule inconnu'

    def get_montant(self, obj):
        try:
            return float(obj.invoice.total_amount)
        except Exception:
            return float(obj.price or obj.estimated_price_max or 0)

    def get_status(self, obj):
        mapping = {
            'pending': 'en_attente',
            'confirmed': 'en_attente',
            'technician_dispatched': 'en_cours',
            'technician_arrived': 'en_cours',
            'in_progress': 'en_cours',
            'diagnosis_submitted': 'en_cours',
            'awaiting_client_approval': 'en_cours',
            'parts_ordered': 'en_cours',
            'ready_for_pickup': 'en_cours',
            'completed': 'termine',
            'cancelled': 'annule',
        }
        return mapping.get(obj.status, 'en_attente')


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATIONS
# ─────────────────────────────────────────────────────────────────────────────

class NotificationSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    lienType = serializers.CharField(source='lien_type', allow_blank=True)
    lienId = serializers.CharField(source='lien_id', allow_blank=True)

    class Meta:
        model = Notification
        fields = ['id', 'type', 'titre', 'message', 'lu', 'createdAt', 'lienType', 'lienId']


class NotificationStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    nonLues = serializers.IntegerField()
    lues = serializers.IntegerField()
    cetteSemaine = serializers.IntegerField()


# ─────────────────────────────────────────────────────────────────────────────
# VENTES (Marketplace)
# ─────────────────────────────────────────────────────────────────────────────

class AdminVenteSerializer(serializers.ModelSerializer):
    """Sérialise les Commandes pour la vue ventes de l'admin"""
    id = serializers.CharField(read_only=True)
    client = serializers.SerializerMethodField()
    produits = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source='created_at')
    montant = serializers.DecimalField(source='prix_total', max_digits=10, decimal_places=2)
    statut = serializers.CharField(source='status')

    class Meta:
        model = Commande
        fields = ['id', 'client', 'produits', 'date', 'montant', 'statut']

    def get_client(self, obj):
        user = obj.client.user
        return {
            'nom': user.last_name or user.username,
            'prenom': user.first_name,
            'email': user.email,
        }

    def get_produits(self, obj):
        return [
            {
                'nom': ligne.produit.nom,
                'quantite': ligne.quantite,
                'prix_unitaire': float(ligne.prix_unitaire),
            }
            for ligne in obj.lignes.all()
        ]


# ─────────────────────────────────────────────────────────────────────────────
# STATISTIQUES
# ─────────────────────────────────────────────────────────────────────────────

class StatistiquesSerializer(serializers.Serializer):
    """Données pour la page Statistiques"""
    # Revenus
    revenuTotal = serializers.FloatField()
    revenuMois = serializers.FloatField()
    revenuSemaine = serializers.FloatField()

    # Interventions
    interventionsTotal = serializers.IntegerField()
    interventionsMois = serializers.IntegerField()
    interventionsTerminees = serializers.IntegerField()
    interventionsAnnulees = serializers.IntegerField()

    # Utilisateurs
    utilisateursTotal = serializers.IntegerField()
    nouveauxUtilisateursMois = serializers.IntegerField()
    techniciensActifs = serializers.IntegerField()
    clientsActifs = serializers.IntegerField()

    # Marketplace
    commandesTotal = serializers.IntegerField()
    commandesMois = serializers.IntegerField()
    ventesMontantMois = serializers.FloatField()

    # Techniciens
    noteMoyenneTechniciens = serializers.FloatField()

    # Évolution mensuelle
    evolutionMensuelle = serializers.ListField(child=serializers.DictField())