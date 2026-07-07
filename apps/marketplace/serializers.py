from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from django.utils.encoding import force_str, DjangoUnicodeDecodeError
from django.utils.http import urlsafe_base64_decode
from rest_framework_simplejwt.tokens import RefreshToken
from apps.marketplace.models import Produit, Piece, Commande, LigneCommande, Avis, MarketplaceVehicle, MarketplaceOrder, MarketplacePartnerApplication
from apps.users.models import Client, Vendor

User = get_user_model()



# ==================== MARKETPLACE AUTH / PARTNERS ====================

def normalize_marketplace_phone(value: str) -> str:
    value = (value or '').strip().replace(' ', '')
    if value and not value.startswith('+'):
        digits = ''.join(ch for ch in value if ch.isdigit())
        if len(digits) == 9 and digits.startswith(('6', '2')):
            return f'+237{digits}'
        return f'+{digits}' if digits else value
    return value


class MarketplaceAuthUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    partner = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'telephone', 'user_type', 'address', 'is_active', 'partner'
        ]

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_partner(self, obj):
        if hasattr(obj, 'vendor_profile'):
            profile = obj.vendor_profile
            return {
                'id': profile.id,
                'company_name': profile.company_name,
                'business_license': profile.business_license,
                'partner_type': profile.partner_type,
                'approval_status': profile.approval_status,
                'is_verified': profile.is_verified,
                'rejection_reason': profile.rejection_reason,
            }
        latest = obj.marketplace_partner_applications.order_by('-created_at').first() if obj.pk else None
        if latest:
            return MarketplacePartnerApplicationSerializer(latest).data
        return None


class MarketplaceRegisterSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True, required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    telephone = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        password_confirm = attrs.get('password_confirm') or attrs.get('password')
        if attrs['password'] != password_confirm:
            raise serializers.ValidationError({'password_confirm': 'Les mots de passe ne correspondent pas.'})
        email = attrs['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError({'email': 'Cet email est déjà utilisé.'})
        phone = normalize_marketplace_phone(attrs.get('telephone') or attrs.get('phone') or '')
        if not phone:
            raise serializers.ValidationError({'telephone': 'Le téléphone est requis.'})
        if User.objects.filter(telephone=phone).exists():
            raise serializers.ValidationError({'telephone': 'Ce numéro de téléphone est déjà utilisé.'})
        username = (attrs.get('username') or email.split('@')[0]).strip().replace(' ', '_')
        base = username or 'marketplace_user'
        candidate = base
        i = 1
        while User.objects.filter(username__iexact=candidate).exists():
            i += 1
            candidate = f'{base}_{i}'
        attrs['username'] = candidate
        attrs['email'] = email
        attrs['telephone'] = phone
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        validated_data.pop('password_confirm', None)
        validated_data.pop('phone', None)
        user = User(
            username=validated_data.get('username'),
            email=validated_data.get('email'),
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            telephone=validated_data.get('telephone'),
            address=validated_data.get('address', ''),
            user_type='marketplace_customer',
            is_active=True,
        )
        user.set_password(password)
        user.save()
        return user


class MarketplaceLoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    allowed_types = ['marketplace_customer', 'vendor', 'auto_shop', 'administrator']

    def validate(self, attrs):
        login_value = (attrs.get('username') or attrs.get('email') or '').strip()
        if not login_value:
            raise serializers.ValidationError({'username': 'Email, téléphone ou nom d’utilisateur requis.'})
        user = User.objects.filter(email__iexact=login_value).first()
        if not user:
            user = User.objects.filter(telephone=login_value).first()
        if not user:
            user = User.objects.filter(username__iexact=login_value).first()
        if not user or not user.check_password(attrs['password']):
            raise serializers.ValidationError({'detail': 'Identifiants marketplace invalides.'})
        if user.user_type not in self.allowed_types:
            raise serializers.ValidationError({'detail': "Ce compte appartient à l'application intervention. Créez un compte marketplace séparé."})
        if not user.is_active:
            raise serializers.ValidationError({'detail': 'Compte marketplace désactivé.'})
        refresh = RefreshToken.for_user(user)
        attrs['user'] = user
        attrs['access'] = str(refresh.access_token)
        attrs['refresh'] = str(refresh)
        return attrs


class MarketplacePartnerApplicationSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_telephone = serializers.CharField(source='user.telephone', read_only=True)

    class Meta:
        model = MarketplacePartnerApplication
        fields = [
            'id', 'user', 'user_name', 'user_email', 'user_telephone', 'partner_type',
            'company_name', 'business_license', 'contact_phone', 'message', 'status',
            'rejection_reason', 'reviewed_by', 'reviewed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'status', 'rejection_reason', 'reviewed_by', 'reviewed_at', 'created_at', 'updated_at']

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class MarketplacePartnerApplicationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketplacePartnerApplication
        fields = ['partner_type', 'company_name', 'business_license', 'contact_phone', 'message']

    def validate(self, attrs):
        user = self.context['request'].user
        if getattr(user, 'user_type', None) not in ['marketplace_customer', 'vendor', 'auto_shop']:
            raise serializers.ValidationError('Seuls les comptes marketplace peuvent demander une accréditation.')
        if MarketplacePartnerApplication.objects.filter(user=user, status='pending').exists():
            raise serializers.ValidationError('Une demande marketplace est déjà en attente de validation.')
        return attrs

    def create(self, validated_data):
        return MarketplacePartnerApplication.objects.create(user=self.context['request'].user, **validated_data)


class MarketplacePasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.CharField(required=False, allow_blank=True)
    identifier = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        value = (attrs.get('identifier') or attrs.get('email') or '').strip()
        if not value:
            raise serializers.ValidationError({'identifier': 'Ce champ est obligatoire.'})
        attrs['identifier'] = value
        return attrs


class MarketplacePasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'new_password': 'Les mots de passe ne correspondent pas.'})
        return attrs


# ==================== PRODUIT SERIALIZERS ====================

class ProduitSerializer(serializers.ModelSerializer):
    """Serializer pour les produits"""
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    vendeur_name = serializers.CharField(source='vendeur.get_full_name', read_only=True)
    vendeur_username = serializers.CharField(source='vendeur.username', read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    total_sold = serializers.IntegerField(read_only=True)
    average_rating = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Produit
        fields = [
            'id', 'nom', 'description', 'prix', 'stock', 'category',
            'category_display', 'images', 'vendeur', 'vendeur_name',
            'vendeur_username', 'marque', 'reference', 'is_active',
            'is_featured', 'is_in_stock', 'total_sold', 'average_rating',
            'reviews_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'total_sold']
    
    def get_average_rating(self, obj):
        from apps.marketplace.services import get_product_rating
        return get_product_rating(obj)['average']
    
    def get_reviews_count(self, obj):
        return obj.avis.count()


class ProduitListSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour la liste des produits"""
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    vendeur_name = serializers.CharField(source='vendeur.get_full_name', read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Produit
        fields = [
            'id', 'nom', 'prix', 'stock', 'category', 'category_display',
            'vendeur_name', 'is_in_stock', 'is_featured', 'images'
        ]


class ProduitCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer un produit"""
    
    class Meta:
        model = Produit
        fields = [
            'nom', 'description', 'prix', 'stock', 'category',
            'images', 'marque', 'reference', 'is_featured'
        ]
    
    def validate_prix(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le prix doit être supérieur à 0")
        return value
    
    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Le stock ne peut pas être négatif")
        return value
    
    def create(self, validated_data):
        """Créer le produit avec le vendeur depuis le contexte"""
        request = self.context.get('request')
        validated_data['vendeur'] = request.user
        return Produit.objects.create(**validated_data)


class ProduitUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour mettre à jour un produit"""
    
    class Meta:
        model = Produit
        fields = [
            'nom', 'description', 'prix', 'stock', 'category',
            'images', 'marque', 'reference', 'is_active', 'is_featured'
        ]


class ProduitDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour un produit"""
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    vendeur = serializers.SerializerMethodField()
    pieces = serializers.SerializerMethodField()
    rating_details = serializers.SerializerMethodField()
    recent_reviews = serializers.SerializerMethodField()
    
    class Meta:
        model = Produit
        fields = [
            'id', 'nom', 'description', 'prix', 'stock', 'category',
            'category_display', 'images', 'vendeur', 'marque', 'reference',
            'is_active', 'is_featured', 'pieces', 'rating_details',
            'recent_reviews', 'created_at', 'updated_at'
        ]
    
    def get_vendeur(self, obj):
        from apps.users.serializers import VendorSerializer
        if hasattr(obj.vendeur, 'vendor_profile'):
            return VendorSerializer(obj.vendeur.vendor_profile).data
        return {
            'id': obj.vendeur.id,
            'username': obj.vendeur.username,
            'full_name': obj.vendeur.get_full_name()
        }
    
    def get_pieces(self, obj):
        return PieceSerializer(obj.pieces.all(), many=True).data
    
    def get_rating_details(self, obj):
        from apps.marketplace.services import get_product_rating
        return get_product_rating(obj)
    
    def get_recent_reviews(self, obj):
        recent = obj.avis.all()[:5]
        return AvisSerializer(recent, many=True).data


# ==================== PIECE SERIALIZERS ====================

class PieceSerializer(serializers.ModelSerializer):
    """Serializer pour les pièces, enrichi pour marketplace_cartronic."""
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    category = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    seller_id = serializers.SerializerMethodField()
    seller_name = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Piece
        fields = [
            'id', 'nom', 'reference', 'prix', 'stock', 'produit',
            'produit_nom', 'category', 'images', 'seller_id', 'seller_name',
            'rating', 'review_count', 'description', 'compatibilite',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_category(self, obj):
        if obj.produit_id and obj.produit:
            return obj.produit.get_category_display() or obj.produit.category
        return 'Pièce détachée'

    def get_images(self, obj):
        if obj.produit_id and obj.produit and obj.produit.images:
            return obj.produit.images if isinstance(obj.produit.images, list) else []
        return []

    def get_seller_id(self, obj):
        if obj.produit_id and obj.produit and obj.produit.vendeur_id:
            return str(obj.produit.vendeur_id)
        return 'cartronic'

    def get_seller_name(self, obj):
        if obj.produit_id and obj.produit and obj.produit.vendeur_id:
            return obj.produit.vendeur.get_full_name() or obj.produit.vendeur.username
        return 'Cartronic'

    def get_rating(self, obj):
        if obj.produit_id and obj.produit:
            from apps.marketplace.services import get_product_rating
            return get_product_rating(obj.produit)['average']
        return 0

    def get_review_count(self, obj):
        if obj.produit_id and obj.produit:
            return obj.produit.avis.count()
        return 0


class PieceCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer une pièce"""
    
    class Meta:
        model = Piece
        fields = [
            'nom', 'reference', 'prix', 'stock', 'produit',
            'description', 'compatibilite'
        ]
    
    def validate_reference(self, value):
        if Piece.objects.filter(reference=value).exists():
            raise serializers.ValidationError("Cette référence existe déjà")
        return value


# ==================== COMMANDE SERIALIZERS ====================

class LigneCommandeSerializer(serializers.ModelSerializer):
    """Serializer pour les lignes de commande"""
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    produit_image = serializers.SerializerMethodField()
    prix_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = LigneCommande
        fields = [
            'id', 'produit', 'produit_nom', 'produit_image',
            'quantite', 'prix_unitaire', 'prix_total'
        ]
    
    def get_produit_image(self, obj):
        if obj.produit.images:
            return obj.produit.images[0] if isinstance(obj.produit.images, list) else None
        return None


class CommandeSerializer(serializers.ModelSerializer):
    """Serializer pour les commandes"""
    lignes = LigneCommandeSerializer(many=True, read_only=True)
    client_name = serializers.CharField(source='client.user.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    prix_total_avec_livraison = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    nombre_articles = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Commande
        fields = [
            'id', 'date', 'client', 'client_name', 'status', 'status_display',
            'payment_status', 'payment_status_display', 'prix_total',
            'frais_livraison', 'prix_total_avec_livraison', 'adresse_livraison',
            'telephone_livraison', 'notes', 'lignes', 'nombre_articles',
            'date_paiement', 'date_expedition', 'date_livraison', 'updated_at'
        ]
        read_only_fields = [
            'id', 'date', 'prix_total', 'date_paiement',
            'date_expedition', 'date_livraison', 'updated_at'
        ]


class CommandeListSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour la liste des commandes"""
    client_name = serializers.CharField(source='client.user.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    nombre_articles = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Commande
        fields = [
            'id', 'date', 'client_name', 'status', 'status_display',
            'prix_total', 'nombre_articles'
        ]


class CommandeCreateSerializer(serializers.Serializer):
    """Serializer pour créer une commande"""
    adresse_livraison = serializers.CharField()
    telephone_livraison = serializers.CharField(required=False)
    frais_livraison = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = serializers.CharField(required=False, allow_blank=True)
    lignes = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField()
        )
    )
    
    def validate_lignes(self, value):
        """Valider que les produits existent et ont du stock"""
        if not value:
            raise serializers.ValidationError("La commande doit contenir au moins un produit")
        
        for ligne in value:
            if 'produit_id' not in ligne or 'quantite' not in ligne:
                raise serializers.ValidationError("Chaque ligne doit contenir produit_id et quantite")
            
            try:
                produit = Produit.objects.get(id=ligne['produit_id'], is_active=True)
                quantite = int(ligne['quantite'])
                
                if quantite <= 0:
                    raise serializers.ValidationError("La quantité doit être supérieure à 0")
                
                if produit.stock < quantite:
                    raise serializers.ValidationError(
                        f"Stock insuffisant pour {produit.nom}. Disponible: {produit.stock}"
                    )
            except Produit.DoesNotExist:
                raise serializers.ValidationError(
                    f"Produit {ligne['produit_id']} introuvable ou inactif"
                )
            except ValueError:
                raise serializers.ValidationError("Quantité invalide")
        
        return value
    
    def create(self, validated_data):
        """Créer la commande et ses lignes"""
        from apps.marketplace.services import create_commande
        client = self.context['request'].user.client_profile
        return create_commande(client, validated_data)


class CommandeUpdateStatusSerializer(serializers.Serializer):
    """Serializer pour mettre à jour le statut d'une commande"""
    status = serializers.ChoiceField(choices=Commande.STATUS_CHOICES)
    notes_admin = serializers.CharField(required=False, allow_blank=True)


# ==================== AVIS SERIALIZERS ====================

class AvisSerializer(serializers.ModelSerializer):
    """Serializer pour les avis"""
    client_name = serializers.CharField(source='client.user.get_full_name', read_only=True)
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    is_verified_purchase = serializers.SerializerMethodField()
    
    class Meta:
        model = Avis
        fields = [
            'id', 'produit', 'produit_nom', 'client', 'client_name',
            'note', 'commentaire', 'is_verified_purchase',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'client']
    
    def get_is_verified_purchase(self, obj):
        return obj.commande is not None


class AvisCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer un avis"""
    
    class Meta:
        model = Avis
        fields = ['produit', 'note', 'commentaire']
    
    def validate_note(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("La note doit être entre 1 et 5")
        return value
    
    def validate(self, data):
        """Vérifier que le client n'a pas déjà laissé un avis"""
        request = self.context.get('request')
        client = getattr(request.user, 'client_profile', None)
        produit = data['produit']
        
        if Avis.objects.filter(client=client, produit=produit).exists():
            raise serializers.ValidationError("Vous avez déjà laissé un avis pour ce produit")
        
        return data
    
    def create(self, validated_data):
        """Créer l'avis avec le client depuis le contexte"""
        request = self.context.get('request')
        validated_data['client'] = request.user.client_profile
        
        # Vérifier si achat vérifié
        commande = Commande.objects.filter(
            client=validated_data['client'],
            lignes__produit=validated_data['produit'],
            status='delivered'
        ).first()
        
        if commande:
            validated_data['commande'] = commande
        
        return Avis.objects.create(**validated_data)


# ==================== STATS SERIALIZERS ====================

class MarketplaceStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques du marketplace"""
    total_produits = serializers.IntegerField()
    total_commandes = serializers.IntegerField()
    commandes_by_status = serializers.DictField()
    revenus = serializers.DictField()
    produits_stock_faible = serializers.IntegerField()

class MarketplaceArticleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = __import__('apps.marketplace.models', fromlist=['MarketplaceArticleType']).MarketplaceArticleType
        fields = ['id', 'code', 'label', 'kind', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

# ==================== MARKETPLACE MOBILE SERIALIZERS ====================

class MarketplaceVehicleSerializer(serializers.ModelSerializer):
    """Serializer aligné sur l'entité Vehicle du frontend marketplace_cartronic."""
    partner_id = serializers.SerializerMethodField()
    partner_name = serializers.CharField(source='partner_display_name', read_only=True)
    bodyType = serializers.CharField(source='body_type', read_only=True)
    reviewCount = serializers.IntegerField(source='review_count', read_only=True)
    isFavorite = serializers.SerializerMethodField()

    class Meta:
        model = MarketplaceVehicle
        fields = [
            'id', 'name', 'brand', 'model', 'year', 'type', 'price',
            'body_type', 'bodyType', 'transmission', 'fuel', 'seats',
            'horsepower', 'features', 'location', 'images', 'rating',
            'review_count', 'reviewCount', 'isFavorite', 'partner_id',
            'partner_name', 'description', 'is_active', 'is_featured',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'partner_id', 'partner_name', 'isFavorite']

    def get_partner_id(self, obj):
        return str(obj.partner_id) if obj.partner_id else 'cartronic'

    def get_isFavorite(self, obj):
        # Les favoris restent gérés côté mobile par AsyncStorage pour ne pas
        # imposer de migration de données aux utilisateurs existants.
        return False


class MarketplaceVehicleCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketplaceVehicle
        fields = [
            'name', 'brand', 'model', 'year', 'type', 'price', 'body_type',
            'transmission', 'fuel', 'seats', 'horsepower', 'features',
            'location', 'images', 'rating', 'review_count', 'partner_name',
            'description', 'is_active', 'is_featured',
        ]

    def create(self, validated_data):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and getattr(user, 'user_type', None) in ['vendor', 'auto_shop', 'administrator']:
            validated_data['partner'] = user
            validated_data.setdefault('partner_name', user.get_full_name() or user.username)
        return MarketplaceVehicle.objects.create(**validated_data)


class MarketplaceOrderSerializer(serializers.ModelSerializer):
    """Serializer aligné sur l'entité Order du frontend marketplace_cartronic."""
    paymentStatus = serializers.CharField(source='payment_status', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    rentalStartDate = serializers.DateTimeField(source='rental_start_date', read_only=True)
    rentalEndDate = serializers.DateTimeField(source='rental_end_date', read_only=True)
    actualPickupDate = serializers.DateTimeField(source='actual_pickup_date', read_only=True)
    actualReturnDate = serializers.DateTimeField(source='actual_return_date', read_only=True)
    paymentMethod = serializers.CharField(source='payment_method', read_only=True)
    paymentDate = serializers.DateTimeField(source='payment_date', read_only=True)
    shippingAddress = serializers.JSONField(source='shipping_address', read_only=True)
    shippingMethod = serializers.JSONField(source='shipping_method', read_only=True)
    deliveryFee = serializers.DecimalField(source='delivery_fee', max_digits=10, decimal_places=2, read_only=True)
    cancellationReason = serializers.CharField(source='cancellation_reason', read_only=True)
    timeline = serializers.SerializerMethodField()

    class Meta:
        model = MarketplaceOrder
        fields = [
            'id', 'type', 'status', 'payment_status', 'paymentStatus', 'items',
            'total', 'currency', 'created_at', 'createdAt', 'updated_at', 'updatedAt',
            'rental_start_date', 'rentalStartDate', 'rental_end_date', 'rentalEndDate',
            'actual_pickup_date', 'actualPickupDate', 'actual_return_date', 'actualReturnDate',
            'payment_method', 'paymentMethod', 'payment_date', 'paymentDate',
            'shipping_address', 'shippingAddress', 'shipping_method', 'shippingMethod',
            'delivery_fee', 'deliveryFee', 'subtotal', 'notes', 'cancellation_reason',
            'cancellationReason', 'timeline',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_timeline(self, obj):
        events = [
            ('pending', 'Commande créée', obj.created_at),
        ]
        if obj.payment_status == 'paid' and obj.payment_date:
            events.append(('confirmed', 'Paiement reçu', obj.payment_date))
        if obj.status in ['confirmed', 'ready', 'in_progress', 'delivered', 'completed']:
            events.append(('confirmed', 'Commande confirmée', obj.updated_at))
        if obj.status in ['ready', 'in_progress', 'completed']:
            events.append(('ready', 'Commande prête', obj.updated_at))
        if obj.actual_pickup_date:
            events.append(('in_progress', 'Récupération effectuée', obj.actual_pickup_date))
        if obj.status in ['delivered']:
            events.append(('delivered', 'Commande livrée', obj.updated_at))
        if obj.actual_return_date:
            events.append(('completed', 'Retour effectué', obj.actual_return_date))
        if obj.status in ['cancelled', 'refunded', 'overdue']:
            label = 'Commande annulée' if obj.status == 'cancelled' else ('Commande remboursée' if obj.status == 'refunded' else 'Location en retard')
            events.append((obj.status, label, obj.updated_at))

        seen = set()
        timeline = []
        for status_value, description, date in events:
            key = (status_value, description, date)
            if key in seen:
                continue
            seen.add(key)
            timeline.append({
                'id': f'{obj.id}-{len(timeline) + 1}',
                'status': status_value,
                'description': description,
                'date': date,
                'isActive': True,
            })
        return timeline


class MarketplaceOrderCreateSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=MarketplaceOrder.TYPE_CHOICES)
    items = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    rentalStartDate = serializers.DateTimeField(required=False, allow_null=True)
    rentalEndDate = serializers.DateTimeField(required=False, allow_null=True)
    paymentMethod = serializers.ChoiceField(choices=MarketplaceOrder.PAYMENT_METHOD_CHOICES, required=False, allow_blank=True)
    shippingAddress = serializers.JSONField(required=False)
    shippingMethod = serializers.JSONField(required=False)
    deliveryFee = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False, default=0)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, default=0)
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        order_type = attrs['type']
        items = attrs['items']

        if order_type in ['vehicle_sale', 'vehicle_rental']:
            if len(items) != 1:
                raise serializers.ValidationError({'items': 'Une commande véhicule doit contenir un seul véhicule.'})
            vehicle_id = str(items[0].get('id') or items[0].get('vehicle_id') or '').strip()
            if not vehicle_id:
                raise serializers.ValidationError({'items': 'Identifiant du véhicule manquant.'})
            try:
                vehicle = MarketplaceVehicle.objects.get(id=vehicle_id, is_active=True)
            except MarketplaceVehicle.DoesNotExist:
                raise serializers.ValidationError({'items': f'Véhicule {vehicle_id} introuvable ou inactif.'})
            if order_type == 'vehicle_sale' and vehicle.type != 'sale':
                raise serializers.ValidationError({'type': 'Ce véhicule n’est pas disponible à la vente.'})
            if order_type == 'vehicle_rental':
                if vehicle.type != 'rental':
                    raise serializers.ValidationError({'type': 'Ce véhicule n’est pas disponible à la location.'})
                if not attrs.get('rentalStartDate') or not attrs.get('rentalEndDate'):
                    raise serializers.ValidationError({'rentalStartDate': 'Les dates de location sont requises.'})
                if attrs['rentalEndDate'] <= attrs['rentalStartDate']:
                    raise serializers.ValidationError({'rentalEndDate': 'La date de fin doit être après la date de début.'})
                conflicts = False
                for order in MarketplaceOrder.objects.filter(
                    type='vehicle_rental',
                    status__in=['pending', 'confirmed', 'ready', 'in_progress'],
                    rental_start_date__lt=attrs['rentalEndDate'],
                    rental_end_date__gt=attrs['rentalStartDate'],
                ):
                    if any(str(item.get('id')) == vehicle_id for item in (order.items or [])):
                        conflicts = True
                        break
                if conflicts:
                    raise serializers.ValidationError({'rentalStartDate': 'Ce véhicule est déjà réservé sur cette période.'})

        if order_type == 'part':
            for item in items:
                part_id = str(item.get('id') or item.get('part_id') or '').strip()
                if not part_id:
                    raise serializers.ValidationError({'items': 'Identifiant de pièce manquant.'})
                try:
                    piece = Piece.objects.get(id=part_id)
                except Piece.DoesNotExist:
                    raise serializers.ValidationError({'items': f'Pièce {part_id} introuvable.'})
                try:
                    quantity = int(item.get('quantity', 1))
                except (TypeError, ValueError):
                    raise serializers.ValidationError({'items': f'Quantité invalide pour {piece.nom}.'})
                if quantity <= 0:
                    raise serializers.ValidationError({'items': 'La quantité doit être supérieure à 0.'})
                if piece.stock < quantity:
                    raise serializers.ValidationError({'items': f'Stock insuffisant pour {piece.nom}. Disponible: {piece.stock}'})

        return attrs

    def create(self, validated_data):
        request = self.context['request']
        client = getattr(request.user, 'client_profile', None)
        items = validated_data['items']
        order_type = validated_data['type']

        if order_type == 'part':
            for item in items:
                piece = Piece.objects.get(id=str(item.get('id') or item.get('part_id')))
                quantity = int(item.get('quantity', 1))
                piece.stock = max(0, piece.stock - quantity)
                piece.save(update_fields=['stock', 'updated_at'])

        payment_method = validated_data.get('paymentMethod') or ''
        order = MarketplaceOrder.objects.create(
            client=client,
            marketplace_user=request.user,
            type=order_type,
            status='confirmed' if payment_method else 'pending',
            payment_status='pending' if payment_method == 'cash' or not payment_method else 'paid',
            items=items,
            total=validated_data['total'],
            rental_start_date=validated_data.get('rentalStartDate'),
            rental_end_date=validated_data.get('rentalEndDate'),
            payment_method=payment_method,
            payment_date=timezone.now() if payment_method and payment_method != 'cash' else None,
            shipping_address=validated_data.get('shippingAddress') or {},
            shipping_method=validated_data.get('shippingMethod') or {},
            delivery_fee=validated_data.get('deliveryFee') or 0,
            subtotal=validated_data.get('subtotal') or validated_data['total'],
            notes=validated_data.get('notes') or '',
        )
        return order


class MarketplaceOrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=MarketplaceOrder.STATUS_CHOICES)
    actualPickupDate = serializers.DateTimeField(required=False, allow_null=True)
    actualReturnDate = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    cancellationReason = serializers.CharField(required=False, allow_blank=True)

