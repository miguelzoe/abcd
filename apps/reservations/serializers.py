from rest_framework import serializers
from django.contrib.gis.geos import Point
from django.utils import timezone
from django.db.models import Q
from datetime import datetime
from apps.reservations.models import (
    Reservation, Evaluation, Diagnostic, 
    TripTracking, ChatMessage, ChatConversation,
    TechnicianAvailability, WorkProgress, Invoice, ReservationReminder
)
from apps.vehicles.models import Vehicle  # IMPORT CORRIGÉ
from apps.users.models import Client, Technician
from apps.reservations.services import ACTIVE_RESERVATION_STATUSES, is_technician_available_at, get_reservation_revenue, count_slot_bookings


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
            slot_start = timezone.make_aware(datetime.combine(target_date, obj.start_time), timezone.get_current_timezone())
            slot_end = timezone.make_aware(datetime.combine(target_date, obj.end_time), timezone.get_current_timezone())
            used = count_slot_bookings(obj.technician, slot_start, slot_end)
            return max(0, int(obj.max_bookings or 1) - used)
        except Exception:
            return None

    def validate(self, attrs):
        # Alias mobile
        if attrs.get('max_spots') is not None:
            attrs['max_bookings'] = attrs.pop('max_spots')

        if attrs.get('max_bookings') is None:
            attrs['max_bookings'] = 1

        instance = getattr(self, 'instance', None)
        request = self.context.get('request')
        technician = getattr(instance, 'technician', None)
        if technician is None and request and getattr(request.user, 'user_type', None) == 'technician':
            technician = getattr(request.user, 'technician_profile', None)

        target_date = attrs.get('date') or getattr(instance, 'date', None)
        st = attrs.get('start_time') or getattr(instance, 'start_time', None)
        et = attrs.get('end_time') or getattr(instance, 'end_time', None)

        if st and et and et <= st:
            raise serializers.ValidationError({'end_time': "L'heure de fin doit être après l'heure de début."})

        if technician and target_date and st and et:
            qs = TechnicianAvailability.objects.filter(technician=technician, date=target_date)
            if instance is not None:
                qs = qs.exclude(pk=instance.pk)

            if qs.filter(start_time=st).exists():
                raise serializers.ValidationError({'start_time': 'Un créneau identique existe déjà pour cette heure.'})

            if qs.filter(start_time__lt=et, end_time__gt=st).exists():
                raise serializers.ValidationError({'start_time': 'Ce créneau chevauche un créneau déjà existant.'})

        return attrs

    def create(self, validated_data):
        # Idempotent create: if the technician taps a default slot already present,
        # update it instead of raising a database integrity error.
        technician = validated_data.get('technician')
        date = validated_data.get('date')
        start_time = validated_data.get('start_time')
        if technician and date and start_time:
            existing = TechnicianAvailability.objects.filter(
                technician=technician, date=date, start_time=start_time
            ).first()
            if existing:
                for attr, value in validated_data.items():
                    if attr != 'technician':
                        setattr(existing, attr, value)
                existing.save()
                return existing
        return super().create(validated_data)


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
            'pricing_details', 'pricing_version',
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
    revenue = serializers.SerializerMethodField()
    
    class Meta:
        model = Reservation
        fields = [
            'id', 'client_name', 'technician_name', 'vehicle_info',
            'service_type', 'service_type_display', 'urgency_level',
            'date', 'status', 'status_display', 'intervention_type',
            'price', 'revenue', 'has_evaluation', 'cancellation_reason', 'cancelled_at', 'created_at'
        ]
    
    def get_vehicle_info(self, obj):
        if obj.vehicle:
            return f"{obj.vehicle.brand} {obj.vehicle.model} {obj.vehicle.year}"
        return None
    
    def get_has_evaluation(self, obj):
        return hasattr(obj, 'evaluation')

    def get_revenue(self, obj):
        return float(get_reservation_revenue(obj))


class ReservationCreateSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(write_only=True, required=True)
    longitude = serializers.FloatField(write_only=True, required=True)
    vehicle_id = serializers.IntegerField(required=False, allow_null=True)
    technician_id = serializers.IntegerField(required=False, allow_null=True)
    # Compat: ancienne version mobile envoyait preferred_technician_id
    preferred_technician_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    availability_id = serializers.IntegerField(required=False, allow_null=True)
    specialization = serializers.CharField(required=False, allow_blank=True, write_only=True)
    service_id = serializers.CharField(required=False, allow_blank=True, write_only=True)
    # Backward compatible only. The mobile app no longer asks the driver for these.
    pieces_oem = serializers.BooleanField(required=False, default=False, write_only=True)
    zone_deplacement = serializers.CharField(required=False, allow_blank=True, default='', write_only=True)
    
    class Meta:
        model = Reservation
        fields = [
            'vehicle_id', 'technician_id', 'preferred_technician_id', 'availability_id',
            'service_type', 'intervention_type', 'urgency_level', 'specialization', 'service_id',
            'pieces_oem', 'zone_deplacement',
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
        
        service_id = data.pop('service_id', None)
        if service_id:
            # Le mobile envoie l'id du service tarifaire exact après pré-devis.
            # On l'enregistre dans intervention_type pour que le moteur de prix,
            # l'historique et les stats utilisent le même référentiel.
            data['intervention_type'] = service_id
        if not data.get('intervention_type'):
            data['intervention_type'] = 'diagnostic_obd'
        
        return data
    
    def create(self, validated_data):
        latitude = validated_data.pop('latitude')
        longitude = validated_data.pop('longitude')
        vehicle_id = validated_data.pop('vehicle_id', None)
        technician_id = validated_data.pop('technician_id', None)
        if not technician_id:
            technician_id = validated_data.pop('preferred_technician_id', None)
        availability_id = validated_data.pop('availability_id', None)
        requested_specialization = (validated_data.pop('specialization', '') or validated_data.get('intervention_type') or '').strip()
        # The client must not manually choose tariff parameters. Keep legacy payload keys
        # accepted, but compute displacement automatically from technician/client GPS.
        pieces_oem = False
        validated_data.pop('pieces_oem', None)
        validated_data.pop('zone_deplacement', None)
        zone_deplacement = None

        validated_data['location'] = Point(longitude, latitude, srid=4326)

        request = self.context.get('request')
        validated_data['client'] = request.user.client_profile

        if vehicle_id:
            try:
                vehicle = Vehicle.objects.filter(
                    Q(id=vehicle_id),
                    Q(client=request.user.client_profile) | Q(proprietaires=request.user.client_profile)
                ).distinct().get()
                validated_data['vehicle'] = vehicle
            except Vehicle.DoesNotExist:
                raise serializers.ValidationError({'vehicle_id': 'Véhicule introuvable pour ce client.'})

        service_type = validated_data.get('service_type')

        # Règle métier Cartronic : en panne urgente, le client doit choisir
        # le technicien disponible avant d'envoyer la demande. On ne crée plus
        # d'urgence sans technicien, afin d'éviter une affectation ambiguë.
        if service_type == 'emergency' and not technician_id:
            raise serializers.ValidationError({
                'technician_id': 'Choisissez d’abord le technicien disponible qui interviendra.'
            })

        if availability_id:
            try:
                slot = TechnicianAvailability.objects.select_related('technician').get(id=availability_id, is_available=True)
            except TechnicianAvailability.DoesNotExist:
                raise serializers.ValidationError({'availability_id': 'Créneau indisponible ou introuvable.'})
            reservation_dt = validated_data.get('date')
            if reservation_dt.date() != slot.date or not (slot.start_time <= reservation_dt.time() < slot.end_time):
                raise serializers.ValidationError({'date': 'La date ne correspond pas au créneau choisi.'})
            technician_id = slot.technician_id

        technician = None
        if technician_id:
            try:
                technician = Technician.objects.get(id=technician_id)
            except Technician.DoesNotExist:
                raise serializers.ValidationError({'technician_id': 'Technicien introuvable.'})

            if service_type == 'emergency':
                if technician.status != 'available' or not technician.user.is_available:
                    raise serializers.ValidationError({'technician_id': 'Ce technicien vient de passer occupé. Relancez la recherche.'})

            if service_type in ['scheduled_maintenance', 'preventive_maintenance', 'specific_repair', 'diagnosis']:
                if not is_technician_available_at(technician, validated_data.get('date')):
                    raise serializers.ValidationError({'date': 'Ce créneau est déjà occupé pour ce technicien.'})

        reservation = Reservation.objects.create(**validated_data)

        if technician:
            from apps.reservations.services import assign_technician_to_reservation
            from apps.reservations.models import ChatConversation
            assign_technician_to_reservation(technician, reservation)
            ChatConversation.objects.get_or_create(reservation=reservation)

        from apps.reservations.services import assign_nearest_technician
        if not reservation.technician:
            radius = 100 if service_type == 'emergency' else 50
            assign_nearest_technician(
                reservation,
                specialization=requested_specialization,
                radius_km=radius
            )

        # Tarification automatique Cartronic: estimation durable enregistrée dans la réservation.
        try:
            from apps.reservations.pricing import calculate_reservation_quote
            quote = calculate_reservation_quote(
                reservation,
                pieces_oem=pieces_oem,
                zone_deplacement=zone_deplacement,
            )
            exact_price = quote.get('prix_exact') or quote.get('client_amount') or quote.get('fourchette_max')
            # Compatibility: min/max are kept equal to the final exact amount.
            reservation.estimated_price_min = exact_price
            reservation.estimated_price_max = exact_price
            reservation.price = exact_price
            reservation.pricing_details = quote
            reservation.pricing_version = quote.get('pricing_version', '')
            reservation.save(update_fields=[
                'estimated_price_min', 'estimated_price_max', 'pricing_details', 'pricing_version', 'price', 'updated_at'
            ])
        except Exception as exc:
            print('[PRICING][ERROR]', repr(exc))

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
            'pricing_details', 'pricing_version',
            'includes_towing', 'towing_distance_km', 'notes',
            'evaluation', 'diagnostic', 'trip_tracking', 'work_progress', 'invoice',
            'can_be_cancelled', 'requires_client_approval',
            'cancelled_at', 'cancelled_by', 'cancellation_reason',
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


class ReservationReminderSerializer(serializers.ModelSerializer):
    reservation_title = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()
    is_sent = serializers.SerializerMethodField()

    class Meta:
        model = ReservationReminder
        fields = [
            'id', 'reservation', 'reservation_title', 'reminder_type',
            'scheduled_for', 'title', 'body', 'data', 'sent_at', 'read_at',
            'is_sent', 'is_read', 'created_at'
        ]
        read_only_fields = (
            'id', 'reservation', 'reservation_title', 'reminder_type',
            'scheduled_for', 'title', 'body', 'data', 'sent_at', 'read_at',
            'is_sent', 'is_read', 'created_at'
        )

    def get_reservation_title(self, obj):
        try:
            return f"{obj.reservation.get_service_type_display()} #{obj.reservation_id}"
        except Exception:
            return f"Réservation #{obj.reservation_id}"

    def get_is_read(self, obj):
        return obj.read_at is not None

    def get_is_sent(self, obj):
        return obj.sent_at is not None


class ReservationStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    by_status = serializers.DictField()
    by_service_type = serializers.DictField()
    avg_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)