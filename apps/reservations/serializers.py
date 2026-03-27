from rest_framework import serializers
from django.contrib.gis.geos import Point
from django.utils import timezone
from datetime import datetime
from apps.reservations.models import (
    Reservation, Evaluation, Diagnostic, 
    TripTracking, ChatMessage, ChatConversation,
    TechnicianAvailability, WorkProgress, Invoice
)
from apps.vehicles.models import Vehicle  # IMPORT CORRIGÉ
from apps.users.models import Client, Technician


# ==================== VEHICLE SERIALIZERS ====================

class VehicleSerializer(serializers.ModelSerializer):
    next_service_due = serializers.SerializerMethodField()
    
    class Meta:
        model = Vehicle
        fields = [
            'id', 'brand', 'model', 'year', 'license_plate',
            'vehicle_type', 'mileage', 'vin', 'color', 'price', 'status',
            'last_service_date', 'last_service_mileage',
            'next_service_due', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_next_service_due(self, obj):
        return obj.next_service_due


# ==================== DIAGNOSTIC SERIALIZERS ====================

class DiagnosticSerializer(serializers.ModelSerializer):
    technician_name = serializers.CharField(source='technician.user.get_full_name', read_only=True)
    
    class Meta:
        model = Diagnostic
        fields = [
            'id', 'reservation', 'technician', 'technician_name',
            'identified_issue', 'severity', 'symptoms_found', 'obd_codes',
            'parts_needed', 'estimated_repair_time_hours',
            'estimated_labor_cost', 'estimated_parts_cost', 'estimated_total_cost',
            'can_repair_onsite', 'recommended_repair_location', 'repair_location_reason',
            'photos', 'videos', 'detailed_report', 'recommendations',
            'requires_immediate_attention', 'safe_to_drive',
            'client_approved', 'client_approval_date', 'client_comments',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'technician']


class DiagnosticCreateSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Diagnostic
        fields = [
            'reservation', 'identified_issue', 'severity', 'symptoms_found',
            'obd_codes', 'parts_needed', 'estimated_repair_time_hours',
            'estimated_labor_cost', 'estimated_parts_cost', 'estimated_total_cost',
            'can_repair_onsite', 'recommended_repair_location', 'repair_location_reason',
            'photos', 'videos', 'detailed_report', 'recommendations',
            'requires_immediate_attention', 'safe_to_drive'
        ]
    
    def validate_reservation(self, value):
        if value.status not in ['in_progress', 'technician_arrived']:
            raise serializers.ValidationError("Le diagnostic ne peut être soumis que pendant l'intervention")
        
        if hasattr(value, 'diagnostic'):
            raise serializers.ValidationError("Un diagnostic existe déjà")
        
        return value
    
    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['technician'] = request.user.technician_profile
        
        diagnostic = Diagnostic.objects.create(**validated_data)
        
        diagnostic.reservation.status = 'diagnosis_submitted'
        if not diagnostic.can_repair_onsite:
            diagnostic.reservation.status = 'awaiting_client_approval'
        diagnostic.reservation.save()
        
        return diagnostic


# ==================== TRIP TRACKING SERIALIZERS ====================

class TripTrackingSerializer(serializers.ModelSerializer):
    technician_latitude = serializers.SerializerMethodField()
    technician_longitude = serializers.SerializerMethodField()
    
    class Meta:
        model = TripTracking
        fields = [
            'id', 'reservation', 'technician_latitude', 'technician_longitude',
            'estimated_arrival_time', 'distance_remaining_km', 'travel_duration_minutes',
            'status', 'started_at', 'arrived_at', 'updated_at'
        ]
        read_only_fields = ['id', 'updated_at']
    
    def get_technician_latitude(self, obj):
        if obj.technician_current_location:
            return obj.technician_current_location.y
        return None
    
    def get_technician_longitude(self, obj):
        if obj.technician_current_location:
            return obj.technician_current_location.x
        return None


# ==================== WORK PROGRESS SERIALIZERS ====================

class WorkProgressSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = WorkProgress
        fields = [
            'id', 'reservation', 'status', 'status_display',
            'description', 'photos', 'videos',
            'client_notified', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


# ==================== CHAT SERIALIZERS ====================

class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.get_full_name', read_only=True)
    sender_type = serializers.CharField(source='sender.user_type', read_only=True)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatMessage
        fields = [
            'id', 'conversation', 'sender', 'sender_name', 'sender_type',
            'message_type', 'content', 'attachment_url',
            'latitude', 'longitude', 'is_read', 'read_at', 'created_at'
        ]
        read_only_fields = ['id', 'sender', 'created_at']
    
    def get_latitude(self, obj):
        if obj.location:
            return obj.location.y
        return None
    
    def get_longitude(self, obj):
        if obj.location:
            return obj.location.x
        return None


# ==================== AVAILABILITY SERIALIZERS ====================

class TechnicianAvailabilitySerializer(serializers.ModelSerializer):

    """Disponibilités technicien.

    Important pour le mobile:
    - ne pas exiger l'envoi du champ `technician` (déduit du user connecté)
    - accepter l'alias `max_spots` utilisé par l'UI
    - exposer `remaining_spots` pour l'affichage
    """

    max_spots = serializers.IntegerField(write_only=True, required=False, min_value=1)
    remaining_spots = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = TechnicianAvailability
        fields = [
            'id', 'technician', 'date', 'start_time', 'end_time',
            'is_available', 'max_bookings', 'max_spots', 'remaining_spots', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'technician']

    def get_remaining_spots(self, obj):
        try:
            target_date = obj.date
            slot_start = datetime.combine(target_date, obj.start_time)
            slot_end = datetime.combine(target_date, obj.end_time)

            used = Reservation.objects.filter(
                technician=obj.technician,
                date__gte=slot_start,
                date__lte=slot_end,
                status__in=['confirmed', 'technician_dispatched', 'technician_arrived', 'in_progress']
            ).count()
            return max(0, int(obj.max_bookings or 0) - used)
        except Exception:
            return None

    def validate(self, attrs):
        # Alias mobile
        if attrs.get('max_spots') is not None:
            attrs['max_bookings'] = attrs.pop('max_spots')

        if attrs.get('max_bookings') is None:
            attrs['max_bookings'] = 1

        st = attrs.get('start_time')
        et = attrs.get('end_time')
        if st and et and et <= st:
            raise serializers.ValidationError({'end_time': "L'heure de fin doit être après l'heure de début."})

        return attrs


# ==================== INVOICE SERIALIZERS ====================

class InvoiceSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'reservation', 'towing_cost', 'diagnosis_cost',
            'parts_cost', 'labor_cost', 'subtotal', 'tax_rate',
            'tax_amount', 'total_amount', 'amount_paid', 'balance_due',
            'payment_status', 'line_items',
            'warranty_months_parts', 'warranty_months_labor',
            'notes', 'issued_at', 'paid_at'
        ]
        read_only_fields = ['id', 'issued_at']


# ==================== EVALUATION SERIALIZERS ====================

class EvaluationSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.user.get_full_name', read_only=True)
    technician_name = serializers.CharField(source='technician.user.get_full_name', read_only=True)
    
    class Meta:
        model = Evaluation
        fields = [
            'id', 'reservation', 'note', 'commentaire',
            'client', 'client_name', 'technician', 'technician_name',
            'response_time_rating', 'diagnosis_quality_rating',
            'communication_rating', 'professionalism', 'value_for_money',
            'punctuality', 'quality', 'would_recommend', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'client', 'technician']


class EvaluationCreateSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Evaluation
        fields = [
            'reservation', 'note', 'commentaire',
            'response_time_rating', 'diagnosis_quality_rating',
            'communication_rating', 'professionalism', 'value_for_money',
            'would_recommend'
        ]
    
    def validate_reservation(self, value):
        if value.status != 'completed':
            raise serializers.ValidationError("La réservation doit être terminée")
        
        if hasattr(value, 'evaluation'):
            raise serializers.ValidationError("Cette réservation a déjà été évaluée")
        
        if not value.technician:
            raise serializers.ValidationError("Pas de technicien assigné")
        
        return value
    
    def create(self, validated_data):
        reservation = validated_data['reservation']
        validated_data['client'] = reservation.client
        validated_data['technician'] = reservation.technician
        
        evaluation = Evaluation.objects.create(**validated_data)
        
        from apps.reservations.services import update_technician_rating
        update_technician_rating(reservation.technician)
        
        return evaluation


# ==================== RESERVATION SERIALIZERS ====================

class ReservationSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.user.get_full_name', read_only=True)
    client_telephone = serializers.CharField(source='client.user.telephone', read_only=True)
    technician_name = serializers.CharField(source='technician.user.get_full_name', read_only=True)
    technician_telephone = serializers.CharField(source='technician.user.telephone', read_only=True)
    
    vehicle = VehicleSerializer(read_only=True)
    evaluation = EvaluationSerializer(read_only=True)
    diagnostic = DiagnosticSerializer(read_only=True)
    trip_tracking = TripTrackingSerializer(read_only=True)
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    service_type_display = serializers.CharField(source='get_service_type_display', read_only=True)
    urgency_display = serializers.CharField(source='get_urgency_level_display', read_only=True)
    
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    
    class Meta:
        model = Reservation
        fields = [
            'id', 'client', 'client_name', 'client_telephone',
            'technician', 'technician_name', 'technician_telephone',
            'vehicle', 'service_type', 'service_type_display',
            'intervention_type', 'urgency_level', 'urgency_display',
            'date', 'scheduled_end_time', 'actual_start_time', 'actual_end_time',
            'status', 'status_display', 'description',
            'latitude', 'longitude', 'location_description',
            'symptoms', 'dashboard_warnings', 'can_restart', 'photos',
            'price', 'estimated_price_min', 'estimated_price_max', 'deposit_paid',
            'includes_towing', 'towing_distance_km', 'towing_destination',
            'notes', 'warranty_months',
            'evaluation', 'diagnostic', 'trip_tracking',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_latitude(self, obj):
        if obj.location:
            return obj.location.y
        return None
    
    def get_longitude(self, obj):
        if obj.location:
            return obj.location.x
        return None


class ReservationListSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.user.get_full_name', read_only=True)
    technician_name = serializers.CharField(source='technician.user.get_full_name', read_only=True)
    vehicle_info = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    service_type_display = serializers.CharField(source='get_service_type_display', read_only=True)
    has_evaluation = serializers.SerializerMethodField()
    
    class Meta:
        model = Reservation
        fields = [
            'id', 'client_name', 'technician_name', 'vehicle_info',
            'service_type', 'service_type_display', 'urgency_level',
            'date', 'status', 'status_display', 'intervention_type',
            'price', 'has_evaluation', 'created_at'
        ]
    
    def get_vehicle_info(self, obj):
        if obj.vehicle:
            return f"{obj.vehicle.brand} {obj.vehicle.model} {obj.vehicle.year}"
        return None
    
    def get_has_evaluation(self, obj):
        return hasattr(obj, 'evaluation')


class ReservationCreateSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(write_only=True, required=True)
    longitude = serializers.FloatField(write_only=True, required=True)
    vehicle_id = serializers.IntegerField(required=False, allow_null=True)
    technician_id = serializers.IntegerField(required=False, allow_null=True)
    # Compat: ancienne version mobile envoyait preferred_technician_id
    preferred_technician_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    availability_id = serializers.IntegerField(required=False, allow_null=True)
    
    class Meta:
        model = Reservation
        fields = [
            'vehicle_id', 'technician_id', 'preferred_technician_id', 'availability_id',
            'service_type', 'intervention_type', 'urgency_level',
            'date', 'description', 'latitude', 'longitude', 'location_description',
            'symptoms', 'dashboard_warnings', 'can_restart', 'photos',
            'includes_towing', 'notes'
        ]
    
    def validate_date(self, value):
        if value < timezone.now():
            request = self.context.get('request')
            if request and request.data.get('service_type') not in ['emergency', 'diagnosis']:
                raise serializers.ValidationError("La date doit être dans le futur")
        return value
    
    def validate(self, data):
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        if not (-90 <= latitude <= 90):
            raise serializers.ValidationError({'latitude': 'Latitude invalide'})
        if not (-180 <= longitude <= 180):
            raise serializers.ValidationError({'longitude': 'Longitude invalide'})
        
        if not data.get('intervention_type'):
            data['intervention_type'] = 'diagnostic_general'
        
        return data
    
    def create(self, validated_data):
        latitude = validated_data.pop('latitude')
        longitude = validated_data.pop('longitude')
        vehicle_id = validated_data.pop('vehicle_id', None)
        technician_id = validated_data.pop('technician_id', None)
        if not technician_id:
            technician_id = validated_data.pop('preferred_technician_id', None)
        availability_id = validated_data.pop('availability_id', None)
        
        validated_data['location'] = Point(longitude, latitude, srid=4326)
        
        request = self.context.get('request')
        validated_data['client'] = request.user.client_profile
        
        if vehicle_id:
            try:
                vehicle = Vehicle.objects.get(id=vehicle_id, client=request.user.client_profile)
                validated_data['vehicle'] = vehicle
            except Vehicle.DoesNotExist:
                pass
        
        service_type = validated_data.get('service_type')
        if service_type == 'emergency':
            validated_data['estimated_price_min'] = 25000
            validated_data['estimated_price_max'] = 150000
        elif service_type == 'scheduled_maintenance':
            validated_data['estimated_price_min'] = 65000
            validated_data['estimated_price_max'] = 85000
        
        reservation = Reservation.objects.create(**validated_data)

        # 1) Si un technicien est explicitement choisi, on l'assigne TOUJOURS et on notifie.
        # La disponibilité est gérée côté UX (créneaux) et par la décision du technicien (accept/refuse).
        if technician_id:
            try:
                from apps.users.models import Technician
                from apps.reservations.services import assign_technician_to_reservation
                from apps.reservations.models import ChatConversation

                technician = Technician.objects.get(id=technician_id)
                assign_technician_to_reservation(technician, reservation)

                # Toujours créer la conversation (pour que la messagerie fonctionne immédiatement)
                ChatConversation.objects.get_or_create(reservation=reservation)
            except Exception as e:
                # Ne pas casser la création de réservation, mais laisser une trace dans les logs
                print('[RESERVATION][ERROR] Technician assign failed:', repr(e))

        # 2) Sinon, auto-assignation pour urgences / dépannage
        from apps.reservations.services import assign_nearest_technician
        if not reservation.technician and service_type in ['emergency', 'diagnosis', 'roadside_repair']:
            radius = 100 if service_type == 'emergency' else 50
            assign_nearest_technician(
                reservation,
                specialization=reservation.intervention_type,
                radius_km=radius
            )
        
        return reservation


class ReservationUpdateSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Reservation
        fields = ['date', 'description', 'intervention_type', 'notes']
    
    def validate_date(self, value):
        if value < timezone.now():
            raise serializers.ValidationError("La date doit être dans le futur")
        return value


class ReservationDetailSerializer(serializers.ModelSerializer):
    client = serializers.SerializerMethodField()
    technician = serializers.SerializerMethodField()
    vehicle = VehicleSerializer(read_only=True)
    evaluation = EvaluationSerializer(read_only=True)
    diagnostic = DiagnosticSerializer(read_only=True)
    trip_tracking = TripTrackingSerializer(read_only=True)
    work_progress = WorkProgressSerializer(many=True, read_only=True)
    invoice = InvoiceSerializer(read_only=True)
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    can_be_cancelled = serializers.BooleanField(read_only=True)
    requires_client_approval = serializers.BooleanField(read_only=True)
    
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    
    class Meta:
        model = Reservation
        fields = [
            'id', 'client', 'technician', 'vehicle',
            'service_type', 'intervention_type', 'urgency_level',
            'date', 'status', 'status_display', 'description',
            'latitude', 'longitude', 'location_description',
            'symptoms', 'dashboard_warnings', 'can_restart', 'photos',
            'price', 'estimated_price_min', 'estimated_price_max',
            'includes_towing', 'towing_distance_km', 'notes',
            'evaluation', 'diagnostic', 'trip_tracking', 'work_progress', 'invoice',
            'can_be_cancelled', 'requires_client_approval',
            'created_at', 'updated_at'
        ]
    
    def get_client(self, obj):
        from apps.users.serializers import ClientSerializer
        return ClientSerializer(obj.client).data
    
    def get_technician(self, obj):
        if obj.technician:
            from apps.users.serializers import TechnicianSerializer
            return TechnicianSerializer(obj.technician).data
        return None
    
    def get_latitude(self, obj):
        if obj.location:
            return obj.location.y
        return None
    
    def get_longitude(self, obj):
        if obj.location:
            return obj.location.x
        return None


class ReservationStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    by_status = serializers.DictField()
    by_service_type = serializers.DictField()
    avg_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)