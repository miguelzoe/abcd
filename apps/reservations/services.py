from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.db import transaction
from django.db.models import Avg, Sum, Q
from django.utils import timezone
from datetime import timedelta

from apps.users.models import Technician
from apps.reservations.models import Reservation, Evaluation, TripTracking, WorkProgress


def assign_nearest_technician(reservation, specialization=None, radius_km=50):
    """Assigner le technicien le plus proche"""

    if reservation.is_emergency:
        radius_km = 100

    queryset = Technician.objects.filter(
        user__location__isnull=False,
        user__is_available=True,
        status='available'
    )

    if specialization and specialization != 'diagnostic_general':
        queryset = queryset.filter(specializations__contains=[specialization])

    nearby_technicians = queryset.annotate(
        distance=Distance('user__location', reservation.location)
    ).filter(
        distance__lte=D(km=radius_km)
    ).order_by('distance', '-rating')

    if reservation.service_type == 'scheduled_maintenance':
        for technician in nearby_technicians:
            if is_technician_available_at(technician, reservation.date):
                distance_km = round(technician.distance.km, 1)
                assign_technician_to_reservation(technician, reservation, distance_km=distance_km)
                return technician
        return None
    else:
        if nearby_technicians.exists():
            technician = nearby_technicians.first()
            distance_km = round(technician.distance.km, 1)
            assign_technician_to_reservation(technician, reservation, distance_km=distance_km)
            return technician

    return None


def assign_technician_to_reservation(technician, reservation, distance_km=None):
    """Assigner un technicien"""
    # - on assigne le technicien MAIS la reservation reste en "pending" jusqu'a acceptation
    # - le technicien recoit une notification avec actions Accept/Refuse
    reservation.technician = technician
    if reservation.status == 'pending':
        reservation.save(update_fields=['technician'])
    else:
        reservation.status = 'pending'
        reservation.save(update_fields=['technician', 'status'])

    # ------------------------------
    # Notification au technicien
    # - Creation DB : toujours (pour l'onglet Notifications)
    # - Push Expo  : best effort
    # ------------------------------
    import logging
    from apps.users.models import Notification
    from apps.users.services import send_expo_push_to_user

    logger = logging.getLogger('apps.reservations.services')

    title = 'Nouvelle mission disponible'

    distance_label = f'{distance_km}km' if distance_km is not None else 'proximite'
    body = f"Un client a {distance_label} a besoin de vous - {reservation.get_service_type_display()}"

    data = {
        'type': 'new_reservation',
        'reservation_id': reservation.id,
        'service_type': reservation.service_type,
        'actions': ['accept', 'refuse'],
    }

    # 1) DB notification (critique)
    try:
        Notification.objects.create(user=technician.user, title=title, body=body, data=data)
    except Exception:
        logger.exception(
            '[NOTIFICATION] Echec creation DB notification technicien=%s reservation=%s',
            technician.pk, reservation.pk
        )

    # 2) Push Expo (best effort)
    try:
        send_expo_push_to_user(technician.user, title=title, body=body, data=data)
    except Exception:
        logger.exception(
            '[PUSH] Echec envoi push technicien=%s reservation=%s',
            technician.pk, reservation.pk
        )


def is_technician_available_at(technician, date):
    """Verifier disponibilite"""
    from apps.reservations.models import TechnicianAvailability

    target_date = date.date()
    target_time = date.time()

    availability_exists = TechnicianAvailability.objects.filter(
        technician=technician,
        date=target_date,
        start_time__lte=target_time,
        end_time__gte=target_time,
        is_available=True
    ).exists()

    if not availability_exists:
        return False

    start_window = date - timedelta(hours=2)
    end_window = date + timedelta(hours=2)

    conflicting = Reservation.objects.filter(
        technician=technician,
        date__range=(start_window, end_window),
        status__in=['confirmed', 'in_progress', 'technician_dispatched']
    ).exists()

    return not conflicting


@transaction.atomic
def complete_reservation(reservation, price=None):
    """Terminer une reservation"""
    reservation.status = 'completed'
    reservation.actual_end_time = timezone.now()

    if price:
        reservation.price = price

    reservation.save()

    if reservation.technician:
        technician = reservation.technician
        technician.status = 'available'
        technician.total_interventions += 1
        technician.save()

    WorkProgress.objects.create(
        reservation=reservation,
        status='completed',
        description="Intervention terminee avec succes",
        client_notified=True
    )

    return reservation


@transaction.atomic
def cancel_reservation(reservation, cancelled_by_user):
    """Annuler une reservation"""
    if not reservation.can_be_cancelled:
        raise ValueError(f"Impossible d'annuler au statut '{reservation.get_status_display()}'")

    reservation.status = 'cancelled'
    reservation.cancelled_at = timezone.now()
    reservation.cancelled_by = cancelled_by_user
    reservation.save()

    if reservation.technician and reservation.technician.status == 'busy':
        technician = reservation.technician
        technician.status = 'available'
        technician.save()

    return reservation


@transaction.atomic
def reassign_technician(reservation, force_new=False):
    """Reassigner un technicien"""
    if reservation.technician:
        old_tech = reservation.technician
        old_tech.status = 'available'
        old_tech.save()

        if not force_new:
            reservation.technician = None

    new_technician = assign_nearest_technician(
        reservation,
        specialization=reservation.intervention_type
    )

    return new_technician


def update_technician_rating(technician):
    """Recalculer le rating"""
    avg_rating = Evaluation.objects.filter(
        technician=technician
    ).aggregate(Avg('note'))['note__avg']

    if avg_rating:
        technician.rating = round(avg_rating, 2)
        technician.save()


def get_reservation_stats(client=None, technician=None, start_date=None, end_date=None):
    """Obtenir des statistiques"""
    queryset = Reservation.objects.all()

    if client:
        queryset = queryset.filter(client=client)
    if technician:
        queryset = queryset.filter(technician=technician)
    if start_date:
        queryset = queryset.filter(created_at__gte=start_date)
    if end_date:
        queryset = queryset.filter(created_at__lte=end_date)

    stats = {
        'total': queryset.count(),
        'by_status': {
            'pending': queryset.filter(status='pending').count(),
            'confirmed': queryset.filter(status='confirmed').count(),
            'in_progress': queryset.filter(status='in_progress').count(),
            'completed': queryset.filter(status='completed').count(),
            'cancelled': queryset.filter(status='cancelled').count(),
        },
        'by_service_type': {
            'emergency': queryset.filter(service_type='emergency').count(),
            'scheduled_maintenance': queryset.filter(service_type='scheduled_maintenance').count(),
            'diagnosis': queryset.filter(service_type='diagnosis').count(),
            'roadside_repair': queryset.filter(service_type='roadside_repair').count(),
            'towing': queryset.filter(service_type='towing').count(),
        },
        'avg_price': queryset.filter(
            price__isnull=False
        ).aggregate(Avg('price'))['price__avg'] or 0,
        'total_revenue': queryset.filter(
            status='completed',
            price__isnull=False
        ).aggregate(Sum('price'))['price__sum'] or 0,
    }

    return stats


def update_trip_tracking(trip_tracking, latitude, longitude):
    """Mettre a jour le suivi GPS"""
    from django.contrib.gis.geos import Point

    new_location = Point(longitude, latitude, srid=4326)
    trip_tracking.technician_current_location = new_location

    reservation = trip_tracking.reservation
    distance_km = new_location.distance(reservation.location) * 111
    trip_tracking.distance_remaining_km = round(distance_km, 2)

    travel_time_minutes = int((distance_km / 40) * 60)
    trip_tracking.travel_duration_minutes = travel_time_minutes
    trip_tracking.estimated_arrival_time = timezone.now() + timedelta(minutes=travel_time_minutes)

    if not isinstance(trip_tracking.location_history, list):
        trip_tracking.location_history = []

    trip_tracking.location_history.append({
        'lat': latitude,
        'lng': longitude,
        'timestamp': timezone.now().isoformat()
    })

    trip_tracking.save()

    if distance_km < 0.1 and trip_tracking.status != 'arrived':
        trip_tracking.status = 'arrived'
        trip_tracking.arrived_at = timezone.now()
        trip_tracking.save()

        reservation.status = 'technician_arrived'
        reservation.client_notified_arrival = True
        reservation.save()

    return trip_tracking


def generate_invoice(reservation):
    """Generer une facture"""
    from apps.reservations.models import Invoice

    towing_cost = 0
    if reservation.includes_towing and reservation.towing_distance_km:
        towing_cost = reservation.towing_distance_km * 3000

    diagnosis_cost = 10000 if reservation.service_type in ['diagnosis', 'emergency'] else 0

    parts_cost = 0
    labor_cost = 0
    line_items = []

    if hasattr(reservation, 'diagnostic'):
        diag = reservation.diagnostic
        parts_cost = diag.estimated_parts_cost
        labor_cost = diag.estimated_labor_cost

        for part in diag.parts_needed:
            line_items.append({
                'description': part.get('name', 'Piece'),
                'qty': part.get('qty', 1),
                'unit_price': part.get('price', 0),
                'total': part.get('qty', 1) * part.get('price', 0)
            })
    else:
        labor_cost = reservation.price or 0

    subtotal = towing_cost + diagnosis_cost + parts_cost + labor_cost
    total_amount = subtotal

    invoice = Invoice.objects.create(
        reservation=reservation,
        towing_cost=towing_cost,
        diagnosis_cost=diagnosis_cost,
        parts_cost=parts_cost,
        labor_cost=labor_cost,
        subtotal=subtotal,
        tax_rate=0,
        tax_amount=0,
        total_amount=total_amount,
        amount_paid=reservation.deposit_paid,
        balance_due=total_amount - reservation.deposit_paid,
        payment_status='partial' if reservation.deposit_paid > 0 else 'pending',
        line_items=line_items,
        warranty_months_parts=6,
        warranty_months_labor=3
    )


    return invoice