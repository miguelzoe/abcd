from rest_framework import serializers
from apps.marketplace.models import Produit, Piece, Commande, LigneCommande, Avis
from apps.users.models import Client


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
    """Serializer pour les pièces"""
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    
    class Meta:
        model = Piece
        fields = [
            'id', 'nom', 'reference', 'prix', 'stock', 'produit',
            'produit_nom', 'description', 'compatibilite',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


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
        client = request.user.client_profile
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