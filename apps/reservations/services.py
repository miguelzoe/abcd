from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.db import transaction
from django.db.models import Avg, Sum, Q
from django.utils import timezone
from datetime import timedelta, datetime

from apps.users.models import Technician
from apps.reservations.models import Reservation, Evaluation, TripTracking, WorkProgress

# Créneaux réellement bloquants pour le planning.
# Une demande en `pending` ne bloque pas encore le créneau: le blocage devient effectif
# lorsque le technicien accepte et que la réservation passe à `confirmed`.
ACTIVE_RESERVATION_STATUSES = [
    'confirmed', 'technician_dispatched', 'technician_arrived',
    'in_progress', 'diagnosis_submitted', 'awaiting_client_approval',
    'parts_ordered', 'ready_for_pickup',
]

DEFAULT_SLOT_PAIRS = [
    ('08:00', '10:00'),
    ('10:00', '12:00'),
    ('12:00', '14:00'),
    ('14:00', '16:00'),
    ('16:00', '18:00'),
]


def _parse_slot_time(value):
    return datetime.strptime(value, '%H:%M').time()


def get_default_slot_bounds(target_dt):
    """Retourne les bornes du créneau standard contenant `target_dt`.

    Tous les techniciens sont considérés disponibles par défaut sur ces créneaux,
    sauf si un blocage explicite existe ou si une réservation acceptée occupe le slot.
    """
    if timezone.is_naive(target_dt):
        target_dt = timezone.make_aware(target_dt, timezone.get_current_timezone())
    target_date = target_dt.date()
    target_time = target_dt.time()
    for start, end in DEFAULT_SLOT_PAIRS:
        st = _parse_slot_time(start)
        et = _parse_slot_time(end)
        if st <= target_time < et:
            slot_start = timezone.make_aware(datetime.combine(target_date, st), timezone.get_current_timezone())
            slot_end = timezone.make_aware(datetime.combine(target_date, et), timezone.get_current_timezone())
            return slot_start, slot_end, st, et
    # Fallback: créneau d'une heure autour de l'heure demandée.
    st = target_dt.replace(minute=0, second=0, microsecond=0)
    et = st + timedelta(hours=1)
    return st, et, st.time(), et.time()


def count_slot_bookings(technician, slot_start, slot_end, exclude_reservation_id=None):
    qs = Reservation.objects.filter(
        technician=technician,
        date__gte=slot_start,
        date__lt=slot_end,
        status__in=ACTIVE_RESERVATION_STATUSES,
    )
    if exclude_reservation_id:
        qs = qs.exclude(id=exclude_reservation_id)
    return qs.count()


def ensure_availability_slot_for_reservation(reservation):
    """Bloque explicitement le créneau accepté dans le planning du technicien.

    Le technicien ne devient pas occupé immédiatement pour un rendez-vous planifié;
    seule la cellule choisie passe en indisponible afin que les autres clients ne
    puissent plus choisir le même créneau.
    """
    if not reservation.technician_id or not reservation.date:
        return None
    slot_start, slot_end, st, et = get_default_slot_bounds(reservation.date)
    slot, _ = __import__('apps.reservations.models', fromlist=['TechnicianAvailability']).TechnicianAvailability.objects.get_or_create(
        technician=reservation.technician,
        date=slot_start.date(),
        start_time=st,
        defaults={
            'end_time': et,
            'is_available': False,
            'max_bookings': 1,
            'notes': 'Rendez-vous confirmé automatiquement.',
        },
    )
    changed = False
    if slot.is_available:
        slot.is_available = False
        changed = True
    if slot.end_time != et:
        slot.end_time = et
        changed = True
    if not slot.notes or 'Rendez-vous confirmé' not in slot.notes:
        slot.notes = 'Rendez-vous confirmé automatiquement.'
        changed = True
    if changed:
        slot.save(update_fields=['is_available', 'end_time', 'notes', 'updated_at'])
    return slot


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
                assign_technician_to_reservation(technician, reservation)
                return technician
        return None
    else:
        if nearby_technicians.exists():
            technician = nearby_technicians.first()
            assign_technician_to_reservation(technician, reservation)
            return technician
    
    return None


def assign_technician_to_reservation(technician, reservation):
    """Assigner un technicien"""
    # IMPORTANT: nouvelle logique
    # - on assigne le technicien MAIS la réservation reste en "pending" jusqu'à acceptation
    # - le technicien reçoit une notification avec actions Accept/Refuse
    reservation.technician = technician
    if reservation.status == 'pending':
        reservation.save(update_fields=['technician'])
    else:
        reservation.status = 'pending'
        reservation.save(update_fields=['technician', 'status'])

    # ------------------------------
    # Notification au technicien
    # - Création DB: MUST (pour l’onglet Notifications)
    # - Push Expo: best effort
    # ------------------------------
    from apps.users.models import Notification
    from apps.users.services import send_expo_push_to_user

    try:
        client_user = reservation.client.user
        client_name = client_user.get_full_name() or client_user.username
    except Exception:
        client_name = 'Client'

    title = 'Demande d’intervention'
    body = f"{client_name} • {reservation.get_service_type_display()}"

    data = {
        'type': 'reservation_request',
        'reservation_id': reservation.id,
        'service_type': reservation.service_type,
        'actions': ['accept', 'refuse'],
    }

    # 1) DB notification (critical) — éviter de recréer la même demande non lue à chaque synchro.
    try:
        exists = Notification.objects.filter(
            user=technician.user,
            data__reservation_id=reservation.id,
            data__type='reservation_request',
            read_at__isnull=True,
        ).exists()
        if not exists:
            Notification.objects.create(user=technician.user, title=title, body=body, data=data)
    except Exception as e:
        # Ne pas casser le flux de création de réservation, mais rendre l’erreur visible dans les logs
        print('[NOTIFICATION][ERROR] Failed to create notification:', repr(e))

    # 2) Push (best effort)
    try:
        send_expo_push_to_user(technician.user, title=title, body=body, data=data)
    except Exception:
        pass


def is_technician_available_at(technician, date, exclude_reservation_id=None):
    """Vérifier la disponibilité réelle à un créneau donné.

    Règle métier Cartronic V4:
    - au départ, les créneaux standards 8h-10h, 10h-12h, 12h-14h, 14h-16h, 16h-18h
      sont disponibles pour tous les techniciens actifs;
    - un créneau explicitement bloqué par le technicien devient indisponible;
    - une réservation confirmée/active occupe le créneau;
    - une simple demande en attente ne bloque pas encore le créneau.
    """
    from apps.reservations.models import TechnicianAvailability

    if timezone.is_naive(date):
        date = timezone.make_aware(date, timezone.get_current_timezone())

    slot_start, slot_end, default_start, default_end = get_default_slot_bounds(date)
    target_date = slot_start.date()
    target_time = date.time()

    explicit_slot = TechnicianAvailability.objects.filter(
        technician=technician,
        date=target_date,
        start_time__lte=target_time,
        end_time__gt=target_time,
    ).order_by('-created_at').first()

    if explicit_slot and not explicit_slot.is_available:
        return False

    max_bookings = int(getattr(explicit_slot, 'max_bookings', None) or 1)
    if explicit_slot:
        slot_start = timezone.make_aware(datetime.combine(target_date, explicit_slot.start_time), timezone.get_current_timezone())
        slot_end = timezone.make_aware(datetime.combine(target_date, explicit_slot.end_time), timezone.get_current_timezone())

    bookings_count = count_slot_bookings(technician, slot_start, slot_end, exclude_reservation_id=exclude_reservation_id)
    return bookings_count < max_bookings



def create_planned_reservation_reminders(reservation):
    """Créer les rappels métier après acceptation d'un rendez-vous planifié.

    Règle Cartronic:
    - rien ne doit apparaître immédiatement dans la rubrique Rappels;
    - un rappel apparaît la veille du rendez-vous;
    - un second rappel apparaît le jour du rendez-vous à 7h00;
    - l'envoi push Expo est déclenché par `dispatch_due_reservation_reminders`.
    """
    if not reservation or reservation.is_emergency or not reservation.date or not reservation.technician_id:
        return []

    from apps.reservations.models import ReservationReminder

    local_dt = timezone.localtime(reservation.date)
    day_before = (local_dt - timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)
    day_morning = local_dt.replace(hour=7, minute=0, second=0, microsecond=0)
    now = timezone.now()

    client_user = reservation.client.user
    tech_user = reservation.technician.user
    client_name = client_user.get_full_name() or client_user.username
    tech_name = tech_user.get_full_name() or tech_user.username
    service_label = reservation.get_service_type_display()
    time_label = local_dt.strftime('%H:%M')
    date_label = local_dt.strftime('%d/%m/%Y')

    vehicle_label = ''
    try:
        if reservation.vehicle:
            vehicle_label = f"{reservation.vehicle.brand} {reservation.vehicle.model}".strip()
    except Exception:
        vehicle_label = ''

    location_label = reservation.location_description or 'lieu indiqué dans la réservation'

    rows = []
    definitions = [
        (
            'day_before',
            day_before,
            'Rendez-vous prévu demain',
            f"Votre rendez-vous Cartronic avec {tech_name} est prévu demain à {time_label} pour {service_label}. Préparez votre véhicule et gardez votre téléphone disponible.",
            f"Vous avez une intervention Cartronic demain à {time_label} avec {client_name} pour {service_label}. Merci de vérifier votre disponibilité.",
        ),
        (
            'day_morning',
            day_morning,
            "Votre rendez-vous est aujourd'hui",
            f"Bonjour, votre rendez-vous Cartronic a lieu aujourd'hui à {time_label} avec {tech_name}. Véhicule : {vehicle_label or 'véhicule renseigné'}. Lieu : {location_label}.",
            f"Bonjour, intervention Cartronic aujourd'hui à {time_label} avec {client_name}. Véhicule : {vehicle_label or 'véhicule renseigné'}. Lieu : {location_label}.",
        ),
    ]

    for reminder_type, scheduled_for, title, client_body, tech_body in definitions:
        # Ne pas créer d'ancien rappel ni un rappel immédiat qui apparaîtrait dès la réservation.
        if scheduled_for <= now:
            continue
        for user, body, audience in [(client_user, client_body, 'client'), (tech_user, tech_body, 'technician')]:
            obj, _ = ReservationReminder.objects.update_or_create(
                reservation=reservation,
                user=user,
                reminder_type=reminder_type,
                defaults={
                    'scheduled_for': scheduled_for,
                    'title': title,
                    'body': body,
                    'data': {
                        'type': 'planned_reservation_reminder',
                        'audience': audience,
                        'reservation_id': reservation.id,
                        'service_type': reservation.service_type,
                        'scheduled_for': scheduled_for.isoformat(),
                        'appointment_date': date_label,
                        'appointment_time': time_label,
                        'vehicle': vehicle_label,
                    },
                },
            )
            rows.append(obj)
    return rows

def dispatch_due_reservation_reminders(limit=100):
    """Envoyer les rappels arrivés à échéance vers Notifications + push Expo."""
    from apps.reservations.models import ReservationReminder
    from apps.users.models import Notification
    from apps.users.services import send_expo_push_to_user

    now = timezone.now()
    qs = ReservationReminder.objects.select_related('user', 'reservation').filter(
        sent_at__isnull=True,
        scheduled_for__lte=now,
    ).order_by('scheduled_for')[:limit]

    sent = 0
    for reminder in qs:
        data = dict(reminder.data or {})
        data['reminder_id'] = reminder.id
        Notification.objects.create(
            user=reminder.user,
            title=reminder.title,
            body=reminder.body,
            data=data,
        )
        try:
            send_expo_push_to_user(reminder.user, reminder.title, reminder.body, data=data)
        except Exception:
            pass
        reminder.sent_at = now
        reminder.save(update_fields=['sent_at'])
        sent += 1
    return sent

def get_reservation_revenue(reservation):
    """Montant réellement exploitable pour les stats de revenus.

    Priorité: paiements confirmés -> facture payée/partielle -> prix réservation ->
    montant diagnostic estimé. Cela évite les revenus à zéro quand l'intervention est
    réalisée mais que la facture n'a pas été parfaitement synchronisée.
    """
    from decimal import Decimal
    total = Decimal('0')

    try:
        payments = getattr(reservation, 'payments', None)
        if payments is not None:
            paid = payments.filter(status='confirmed').aggregate(total=Sum('amount'))['total'] or 0
            total += Decimal(str(paid or 0))
    except Exception:
        pass

    if total > 0:
        return total

    try:
        invoice = getattr(reservation, 'invoice', None)
        if invoice and invoice.payment_status in ['paid', 'partial']:
            amount = invoice.amount_paid or invoice.total_amount or 0
            total += Decimal(str(amount or 0))
    except Exception:
        pass

    if total > 0:
        return total

    if reservation.price:
        return Decimal(str(reservation.price or 0))

    try:
        diagnostic = getattr(reservation, 'diagnostic', None)
        if diagnostic and diagnostic.estimated_total_cost:
            return Decimal(str(diagnostic.estimated_total_cost or 0))
    except Exception:
        pass

    return Decimal('0')


def get_reservations_revenue(queryset):
    total = 0
    qs = queryset.select_related('invoice', 'diagnostic').prefetch_related('payments')
    for reservation in qs:
        total += get_reservation_revenue(reservation)
    return total


@transaction.atomic
def complete_reservation(reservation, price=None):
    """Terminer une réservation"""
    reservation.status = 'completed'
    reservation.actual_end_time = timezone.now()
    
    if price:
        reservation.price = price
    elif not reservation.price:
        try:
            diagnostic = getattr(reservation, 'diagnostic', None)
            if diagnostic and diagnostic.estimated_total_cost:
                reservation.price = diagnostic.estimated_total_cost
        except Exception:
            pass
    
    reservation.save()
    
    if reservation.technician:
        technician = reservation.technician
        technician.status = 'available'
        technician.total_interventions += 1
        technician.save()
    
    WorkProgress.objects.create(
        reservation=reservation,
        status='completed',
        description="Intervention terminée avec succès",
        client_notified=True
    )
    
    return reservation


@transaction.atomic
def cancel_reservation(reservation, cancelled_by_user):
    """Annuler une réservation"""
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
    """Réassigner un technicien"""
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
        'total_revenue': get_reservations_revenue(queryset),
    }
    
    return stats


def update_trip_tracking(trip_tracking, latitude, longitude):
    """Mettre à jour le suivi GPS"""
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
    """Générer une facture"""
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
                'description': part.get('name', 'Pièce'),
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