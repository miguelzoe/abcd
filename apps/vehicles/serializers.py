from rest_framework import serializers
from apps.vehicles.models import Vehicle, MaintenanceRecord
from apps.users.models import Client


# ==================== VEHICLE SERIALIZERS ====================

class VehicleSerializer(serializers.ModelSerializer):
    """Serializer de base pour les véhicules"""
    type_vehicule_display = serializers.CharField(source='get_type_vehicule_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    full_name = serializers.CharField(read_only=True)
    age = serializers.IntegerField(read_only=True)
    proprietaires_count = serializers.SerializerMethodField()
    maintenance_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Vehicle
        fields = [
            'id', 'marque', 'modele', 'type_vehicule', 'type_vehicule_display',
            'annee', 'age', 'couleur', 'numero_immatriculation', 'numero_chassis',
            'kilometrage', 'prix', 'statut', 'statut_display', 'notes',
            'full_name', 'proprietaires_count', 'maintenance_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_proprietaires_count(self, obj):
        return obj.proprietaires.count()
    
    def get_maintenance_count(self, obj):
        return obj.maintenance_records.count()


class VehicleListSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour la liste des véhicules"""
    type_vehicule_display = serializers.CharField(source='get_type_vehicule_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    full_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = Vehicle
        fields = [
            'id', 'marque', 'modele', 'full_name', 'type_vehicule',
            'type_vehicule_display', 'annee', 'numero_immatriculation',
            'statut', 'statut_display', 'kilometrage'
        ]


class VehicleCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer un véhicule.

    Accepte au choix les champs FR (marque/modele/type_vehicule/annee/...) ou EN
    (brand/model/vehicle_type/year/...).

    Objectif: éviter les 400 côté frontend quand les clés ne correspondent pas.
    """

    # Champs FR (compat)
    marque = serializers.CharField(source='brand', required=False)
    modele = serializers.CharField(source='model', required=False)
    type_vehicule = serializers.ChoiceField(source='vehicle_type', choices=Vehicle.TYPE_CHOICES, required=False)
    annee = serializers.IntegerField(source='year', required=False)
    couleur = serializers.CharField(source='color', required=False, allow_blank=True)

    numero_immatriculation = serializers.CharField(source='license_plate', required=False, allow_blank=True, allow_null=True)
    numero_chassis = serializers.CharField(source='vin', required=False, allow_blank=True, allow_null=True)
    kilometrage = serializers.IntegerField(source='mileage', required=False)
    prix = serializers.DecimalField(source='price', max_digits=12, decimal_places=2, required=False)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    # Champs EN (natif frontend)
    brand = serializers.CharField(write_only=True, required=False)
    model = serializers.CharField(write_only=True, required=False)
    vehicle_type = serializers.ChoiceField(write_only=True, required=False, choices=Vehicle.TYPE_CHOICES)
    year = serializers.IntegerField(write_only=True, required=False)
    color = serializers.CharField(write_only=True, required=False, allow_blank=True)

    license_plate = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    vin = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    mileage = serializers.IntegerField(write_only=True, required=False)
    price = serializers.DecimalField(write_only=True, max_digits=12, decimal_places=2, required=False)

    class Meta:
        model = Vehicle
        fields = [
            # FR
            'marque', 'modele', 'type_vehicule', 'annee', 'couleur',
            'numero_immatriculation', 'numero_chassis', 'kilometrage',
            'prix', 'notes',
            # EN
            'brand', 'model', 'vehicle_type', 'year', 'color',
            'license_plate', 'vin', 'mileage', 'price',
        ]

    def to_internal_value(self, data):
        d = dict(data)

        # Remap EN -> FR
        if 'brand' in d and 'marque' not in d:
            d['marque'] = d.get('brand')
        if 'model' in d and 'modele' not in d:
            d['modele'] = d.get('model')
        if 'vehicle_type' in d and 'type_vehicule' not in d:
            d['type_vehicule'] = d.get('vehicle_type')

        # Tolérance: valeurs front communes
        vt = d.get('type_vehicule')
        if isinstance(vt, str):
            low = vt.strip().lower()
            if low in ('car', 'voiture'):
                d['type_vehicule'] = 'sedan'
            elif low in ('moto', 'motorbike'):
                d['type_vehicule'] = 'motorcycle'
        if 'year' in d and 'annee' not in d:
            d['annee'] = d.get('year')
        if 'color' in d and 'couleur' not in d:
            d['couleur'] = d.get('color')

        if 'license_plate' in d and 'numero_immatriculation' not in d:
            d['numero_immatriculation'] = d.get('license_plate')
        if 'vin' in d and 'numero_chassis' not in d:
            d['numero_chassis'] = d.get('vin')
        if 'mileage' in d and 'kilometrage' not in d:
            d['kilometrage'] = d.get('mileage')
        if 'price' in d and 'prix' not in d:
            d['prix'] = d.get('price')

        # Normaliser "" -> None pour les champs uniques
        for key in ('numero_immatriculation', 'numero_chassis'):
            if d.get(key) == '':
                d[key] = None

        return super().to_internal_value(d)

    def validate_annee(self, value):
        from datetime import datetime
        current_year = datetime.now().year
        if value < 1900:
            raise serializers.ValidationError("L'année doit être supérieure à 1900")
        if value > current_year + 1:
            raise serializers.ValidationError(f"L'année ne peut pas dépasser {current_year + 1}")
        return value

    def validate_numero_immatriculation(self, value):
        if not value:
            return value
        qs = Vehicle.objects.filter(license_plate=value)
        if qs.exists():
            raise serializers.ValidationError("Un véhicule avec cette immatriculation existe déjà")
        return value

    def validate_numero_chassis(self, value):
        if not value:
            return value
        qs = Vehicle.objects.filter(vin=value)
        if qs.exists():
            raise serializers.ValidationError("Un véhicule avec ce numéro de châssis existe déjà")
        return value


class VehicleUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour mettre à jour un véhicule"""

    couleur = serializers.CharField(source='color', required=False, allow_blank=True)
    kilometrage = serializers.IntegerField(source='mileage', required=False)
    statut = serializers.ChoiceField(source='status', choices=Vehicle.STATUS_CHOICES, required=False)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Vehicle
        fields = ['couleur', 'kilometrage', 'statut', 'notes']


class VehicleDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour un véhicule"""
    type_vehicule_display = serializers.CharField(source='get_type_vehicule_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    full_name = serializers.CharField(read_only=True)
    age = serializers.IntegerField(read_only=True)
    proprietaires = serializers.SerializerMethodField()
    recent_maintenance = serializers.SerializerMethodField()
    total_maintenance_cost = serializers.SerializerMethodField()
    
    class Meta:
        model = Vehicle
        fields = [
            'id', 'marque', 'modele', 'type_vehicule', 'type_vehicule_display',
            'annee', 'age', 'couleur', 'numero_immatriculation', 'numero_chassis',
            'kilometrage', 'prix', 'statut', 'statut_display', 'notes',
            'full_name', 'proprietaires', 'recent_maintenance', 
            'total_maintenance_cost', 'created_at', 'updated_at'
        ]
    
    def get_proprietaires(self, obj):
        from apps.users.serializers import ClientSerializer
        return ClientSerializer(obj.proprietaires.all(), many=True).data
    
    def get_recent_maintenance(self, obj):
        recent = obj.maintenance_records.all()[:5]
        return MaintenanceRecordListSerializer(recent, many=True).data
    
    def get_total_maintenance_cost(self, obj):
        from django.db.models import Sum
        total = obj.maintenance_records.aggregate(Sum('cout'))['cout__sum']
        return float(total) if total else 0


# ==================== MAINTENANCE SERIALIZERS ====================

class MaintenanceRecordSerializer(serializers.ModelSerializer):
    """Serializer pour les maintenances"""
    type_maintenance_display = serializers.CharField(source='get_type_maintenance_display', read_only=True)
    vehicle_name = serializers.CharField(source='vehicle.full_name', read_only=True)
    technician_name = serializers.SerializerMethodField()
    
    class Meta:
        model = MaintenanceRecord
        fields = [
            'id', 'vehicle', 'vehicle_name', 'date', 'type_maintenance',
            'type_maintenance_display', 'description', 'cout',
            'kilometrage_actuel', 'technician', 'technician_name', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_technician_name(self, obj):
        if obj.technician:
            return obj.technician.user.get_full_name() or obj.technician.user.username
        return None


class MaintenanceRecordListSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour la liste des maintenances"""
    type_maintenance_display = serializers.CharField(source='get_type_maintenance_display', read_only=True)
    vehicle_name = serializers.CharField(source='vehicle.full_name', read_only=True)
    
    class Meta:
        model = MaintenanceRecord
        fields = [
            'id', 'vehicle_name', 'date', 'type_maintenance',
            'type_maintenance_display', 'cout', 'kilometrage_actuel'
        ]


class MaintenanceRecordCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer une maintenance"""
    
    class Meta:
        model = MaintenanceRecord
        fields = [
            'vehicle', 'date', 'type_maintenance', 'description',
            'cout', 'kilometrage_actuel', 'technician', 'notes'
        ]
    
    def validate(self, data):
        """Validations croisées"""
        vehicle = data.get('vehicle')
        kilometrage = data.get('kilometrage_actuel')
        
        # Vérifier que le kilométrage est cohérent
        if kilometrage < vehicle.kilometrage:
            raise serializers.ValidationError({
                'kilometrage_actuel': f'Le kilométrage ne peut pas être inférieur à {vehicle.kilometrage} km'
            })
        
        return data
    
    def create(self, validated_data):
        """Créer la maintenance et mettre à jour le véhicule"""
        maintenance = MaintenanceRecord.objects.create(**validated_data)
        
        # Mettre à jour le kilométrage du véhicule
        vehicle = maintenance.vehicle
        if maintenance.kilometrage_actuel > vehicle.kilometrage:
            vehicle.kilometrage = maintenance.kilometrage_actuel
            vehicle.save()
        
        return maintenance


class VehicleStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques de véhicules"""
    total_vehicles = serializers.IntegerField()
    by_type = serializers.DictField()
    by_status = serializers.DictField()
    avg_age = serializers.FloatField()
    total_value = serializers.DecimalField(max_digits=15, decimal_places=2)


class MaintenanceStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques de maintenance"""
    total_maintenance = serializers.IntegerField()
    by_type = serializers.DictField()
    total_cost = serializers.DecimalField(max_digits=15, decimal_places=2)
    avg_cost = serializers.DecimalField(max_digits=10, decimal_places=2)