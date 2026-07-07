from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from django.utils import timezone


PRICING_VERSION = 'cartronic-pricing-v9-prequote-coherent-exact'

GAMME_COEFFICIENTS: Dict[str, Decimal] = {
    'economique': Decimal('1.0'),
    'standard': Decimal('1.3'),
    'suv': Decimal('1.6'),
    '4x4': Decimal('1.8'),
    'utilitaire': Decimal('2.0'),
    'premium': Decimal('2.5'),
}

DEFAULT_VEHICLES: Dict[str, str] = {
    'toyota_corolla': 'economique',
    'toyota_matrix': 'economique',
    'toyota_camry': 'economique',
    'toyota_auris': 'economique',
    'honda_civic': 'economique',
    'honda_jazz': 'economique',
    'nissan_almera': 'economique',
    'peugeot_406': 'economique',
    'mazda_323': 'economique',
    'toyota_avensis': 'standard',
    'toyota_yaris': 'standard',
    'toyota_venza': 'standard',
    'honda_accord': 'standard',
    'hyundai_elantra': 'standard',
    'kia_cerato': 'standard',
    'toyota_rav4': 'suv',
    'toyota_fortuner': 'suv',
    'honda_crv': 'suv',
    'kia_sportage': 'suv',
    'hyundai_tucson': 'suv',
    'mercedes_ml': 'suv',
    'toyota_prado': '4x4',
    'toyota_hilux': '4x4',
    'toyota_landcruiser': '4x4',
    'mitsubishi_l200': '4x4',
    'nissan_navara': '4x4',
    'toyota_hiace': 'utilitaire',
    'toyota_coaster': 'utilitaire',
    'mitsubishi_l300': 'utilitaire',
    'lexus_rx350': 'premium',
    'mercedes_classe_e': 'premium',
    'bmw_serie5': 'premium',
    'audi_q7': 'premium',
}

SERVICES: Dict[str, Dict[str, Any]] = {
    'pneu_reparation': {'label': 'Réparation pneu', 'category': 'specific_repair', 'plancher': 5000, 'plafond': 15000, 'urgence': 'CRITIQUE'},
    'pneu_remplacement': {'label': 'Remplacement pneu', 'category': 'specific_repair', 'plancher': 20000, 'plafond': 80000, 'urgence': 'CRITIQUE'},
    'batterie': {'label': 'Batterie', 'category': 'specific_repair', 'plancher': 15000, 'plafond': 80000, 'urgence': 'CRITIQUE'},
    'alternateur': {'label': 'Alternateur', 'category': 'specific_repair', 'plancher': 40000, 'plafond': 120000, 'urgence': 'CRITIQUE'},
    'demarreur': {'label': 'Démarreur', 'category': 'specific_repair', 'plancher': 30000, 'plafond': 90000, 'urgence': 'CRITIQUE'},
    'surchauffe_thermostat': {'label': 'Surchauffe - thermostat', 'category': 'specific_repair', 'plancher': 20000, 'plafond': 60000, 'urgence': 'CRITIQUE'},
    'surchauffe_pompe_eau': {'label': 'Surchauffe - pompe à eau', 'category': 'specific_repair', 'plancher': 40000, 'plafond': 100000, 'urgence': 'CRITIQUE'},
    'surchauffe_radiateur': {'label': 'Surchauffe - radiateur', 'category': 'specific_repair', 'plancher': 60000, 'plafond': 180000, 'urgence': 'CRITIQUE'},
    'pompe_essence': {'label': 'Pompe à essence', 'category': 'specific_repair', 'plancher': 25000, 'plafond': 80000, 'urgence': 'CRITIQUE'},
    'fuite_refroidissement': {'label': 'Fuite refroidissement', 'category': 'specific_repair', 'plancher': 15000, 'plafond': 50000, 'urgence': 'CRITIQUE'},
    'vidange': {'label': 'Vidange', 'category': 'scheduled_maintenance', 'plancher': 5000, 'plafond': 55000, 'urgence': 'NORMAL'},
    'filtre_air': {'label': 'Filtre à air', 'category': 'preventive_maintenance', 'plancher': 8000, 'plafond': 20000, 'urgence': 'NORMAL'},
    'filtre_carburant': {'label': 'Filtre carburant', 'category': 'preventive_maintenance', 'plancher': 5000, 'plafond': 30000, 'urgence': 'NORMAL'},
    'bougies': {'label': 'Bougies', 'category': 'preventive_maintenance', 'plancher': 5000, 'plafond': 60000, 'urgence': 'NORMAL'},
    'filtre_habitacle': {'label': 'Filtre habitacle', 'category': 'preventive_maintenance', 'plancher': 5000, 'plafond': 25000, 'urgence': 'NORMAL'},
    'liquide_frein': {'label': 'Liquide de frein', 'category': 'preventive_maintenance', 'plancher': 10000, 'plafond': 50000, 'urgence': 'NORMAL'},
    'liquide_refroidissement': {'label': 'Liquide refroidissement', 'category': 'preventive_maintenance', 'plancher': 5000, 'plafond': 45000, 'urgence': 'NORMAL'},
    'diagnostic_obd': {'label': 'Diagnostic OBD', 'category': 'diagnosis', 'plancher': 15000, 'plafond': 25000, 'urgence': 'NORMAL'},
    'entretien_complet': {'label': 'Entretien complet', 'category': 'scheduled_maintenance', 'plancher': 55000, 'plafond': 130000, 'urgence': 'NORMAL'},
    'revision_generale': {'label': 'Révision générale', 'category': 'scheduled_maintenance', 'plancher': 80000, 'plafond': 200000, 'urgence': 'NORMAL'},
    'plaquettes_avant': {'label': 'Plaquettes avant', 'category': 'specific_repair', 'plancher': 5000, 'plafond': 55000, 'urgence': 'MODERE'},
    'plaquettes_disques_avant': {'label': 'Plaquettes + disques avant', 'category': 'specific_repair', 'plancher': 15000, 'plafond': 100000, 'urgence': 'MODERE'},
    'plaquettes_disques_arriere': {'label': 'Plaquettes + disques arrière', 'category': 'specific_repair', 'plancher': 35000, 'plafond': 90000, 'urgence': 'MODERE'},
    'freinage_complet': {'label': 'Freinage complet', 'category': 'specific_repair', 'plancher': 80000, 'plafond': 200000, 'urgence': 'MODERE'},
    'amortisseurs_avant': {'label': 'Amortisseurs avant', 'category': 'specific_repair', 'plancher': 15000, 'plafond': 160000, 'urgence': 'MODERE'},
    'amortisseurs_arriere': {'label': 'Amortisseurs arrière', 'category': 'specific_repair', 'plancher': 15000, 'plafond': 140000, 'urgence': 'MODERE'},
    'rotule_avant': {'label': 'Rotule avant', 'category': 'specific_repair', 'plancher': 5000, 'plafond': 70000, 'urgence': 'MODERE'},
    'triangle_suspension': {'label': 'Triangle suspension', 'category': 'specific_repair', 'plancher': 10000, 'plafond': 120000, 'urgence': 'MODERE'},
    'barre_stabilisatrice': {'label': 'Barre stabilisatrice', 'category': 'specific_repair', 'plancher': 20000, 'plafond': 60000, 'urgence': 'MODERE'},
    'alignement': {'label': 'Alignement', 'category': 'scheduled_maintenance', 'plancher': 10000, 'plafond': 50000, 'urgence': 'NORMAL'},
    'direction_pompe': {'label': 'Pompe de direction', 'category': 'specific_repair', 'plancher': 10000, 'plafond': 180000, 'urgence': 'MODERE'},
    'cremaillere': {'label': 'Crémaillère', 'category': 'specific_repair', 'plancher': 15000, 'plafond': 250000, 'urgence': 'MODERE'},
    'recharge_clim': {'label': 'Recharge climatisation', 'category': 'scheduled_maintenance', 'plancher': 12000, 'plafond': 25000, 'urgence': 'NORMAL'},
    'nettoyage_evaporateur': {'label': 'Nettoyage évaporateur', 'category': 'preventive_maintenance', 'plancher': 15000, 'plafond': 40000, 'urgence': 'NORMAL'},
    'courroie_compresseur': {'label': 'Courroie compresseur', 'category': 'specific_repair', 'plancher': 10000, 'plafond': 30000, 'urgence': 'MODERE'},
    'compresseur_clim': {'label': 'Compresseur climatisation', 'category': 'specific_repair', 'plancher': 60000, 'plafond': 200000, 'urgence': 'MODERE'},
    'condenseur': {'label': 'Condenseur', 'category': 'specific_repair', 'plancher': 40000, 'plafond': 120000, 'urgence': 'MODERE'},
    'ventilateur_chauffage': {'label': 'Ventilateur chauffage', 'category': 'specific_repair', 'plancher': 30000, 'plafond': 80000, 'urgence': 'MODERE'},
    'courroie_distribution': {'label': 'Courroie distribution', 'category': 'specific_repair', 'plancher': 15000, 'plafond': 200000, 'urgence': 'CRITIQUE'},
    'joint_culasse': {'label': 'Joint culasse', 'category': 'specific_repair', 'plancher': 15000, 'plafond': 300000, 'urgence': 'CRITIQUE'},
    'culasse': {'label': 'Culasse', 'category': 'specific_repair', 'plancher': 40000, 'plafond': 500000, 'urgence': 'CRITIQUE'},
    'moteur_complet': {'label': 'Moteur complet', 'category': 'specific_repair', 'plancher': 50000, 'plafond': 1500000, 'urgence': 'CRITIQUE'},
    'embrayage': {'label': 'Embrayage', 'category': 'specific_repair', 'plancher': 20000, 'plafond': 220000, 'urgence': 'MODERE'},
    'boite_manuelle': {'label': 'Boîte manuelle', 'category': 'specific_repair', 'plancher': 40000, 'plafond': 200000, 'urgence': 'MODERE'},
    'boite_automatique': {'label': 'Boîte automatique', 'category': 'specific_repair', 'plancher': 120000, 'plafond': 400000, 'urgence': 'MODERE'},
    'transmission_cardans': {'label': 'Transmission / cardans', 'category': 'specific_repair', 'plancher': 40000, 'plafond': 120000, 'urgence': 'MODERE'},
    'batterie_remplacement': {'label': 'Remplacement batterie', 'category': 'specific_repair', 'plancher': 5000, 'plafond': 70000, 'urgence': 'CRITIQUE'},
    'faisceau_electrique': {'label': 'Faisceau électrique', 'category': 'specific_repair', 'plancher': 20000, 'plafond': 120000, 'urgence': 'MODERE'},
    'capteur_map_maf': {'label': 'Capteur MAP/MAF', 'category': 'specific_repair', 'plancher': 15000, 'plafond': 60000, 'urgence': 'MODERE'},
    'injecteur': {'label': 'Injecteur', 'category': 'specific_repair', 'plancher': 20000, 'plafond': 100000, 'urgence': 'MODERE'},
    'feux_eclairage': {'label': 'Feux / éclairage', 'category': 'specific_repair', 'plancher': 1000, 'plafond': 50000, 'urgence': 'NORMAL'},
    'cle_a_puce': {'label': 'Clé à puce', 'category': 'specific_repair', 'plancher': 35000, 'plafond': 2000000, 'urgence': 'CRITIQUE'},
    'programmation_ecu': {'label': 'Programmation ECU', 'category': 'diagnosis', 'plancher': 25000, 'plafond': 2000000, 'urgence': 'CRITIQUE'},
    'pare_brise': {'label': 'Pare-brise', 'category': 'specific_repair', 'plancher': 50000, 'plafond': 200000, 'urgence': 'MODERE'},
    'vitre_laterale': {'label': 'Vitre latérale', 'category': 'specific_repair', 'plancher': 30000, 'plafond': 120000, 'urgence': 'MODERE'},
    'debosselage': {'label': 'Débosselage', 'category': 'specific_repair', 'plancher': 20000, 'plafond': 80000, 'urgence': 'NORMAL'},
    'peinture_locale': {'label': 'Peinture locale', 'category': 'specific_repair', 'plancher': 40000, 'plafond': 120000, 'urgence': 'NORMAL'},
}


def _key(brand: str, model: str) -> str:
    return f'{(brand or "").strip().lower().replace(" ", "_")}_{(model or "").strip().lower().replace(" ", "_")}'


def _round_500(value: Decimal) -> Decimal:
    return (value / Decimal('500')).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * Decimal('500')


def _soft_vehicle_coefficient(raw: Decimal) -> Decimal:
    """Dampen the algorithm vehicle coefficient for a reservation price.

    The original algorithm coefficients are useful for a full workshop repair including
    labour complexity and parts. For a mobile reservation amount, applying 2.0 or 2.5
    directly makes the price feel punitive. We keep the hierarchy, but soften it.
    Examples: 1.8 -> 1.36, 2.5 -> 1.60.
    """
    if raw <= Decimal('1'):
        return Decimal('1.00')
    return (Decimal('1') + ((raw - Decimal('1')) * Decimal('0.40'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _service_reference_price(service: Dict[str, Any]) -> Decimal:
    """Return one reasonable exact reservation base from the original min/max table.

    The uploaded algorithm stores a plancher and a plafond. Several plafonds include
    expensive parts or exceptional cases (ECU keys, engines, gearboxes), so using the
    midpoint or a large percentage of the spread creates exaggerated reservation prices.
    For the customer-facing reservation, we price the technician mobilization + basic
    labour reference. Parts or exceptional repairs remain justified later by diagnostic.
    """
    plancher = Decimal(str(service['plancher']))
    plafond = Decimal(str(service['plafond']))
    if plafond <= plancher:
        return _round_500(plancher)

    urgency = str(service.get('urgence') or '').upper()
    category = str(service.get('category') or '')
    spread = plafond - plancher

    if category == 'diagnosis':
        weight, spread_cap = Decimal('0.10'), Decimal('10000')
    elif category in ('scheduled_maintenance', 'preventive_maintenance'):
        weight, spread_cap = Decimal('0.12'), Decimal('10000')
    elif urgency == 'CRITIQUE':
        weight, spread_cap = Decimal('0.10'), Decimal('18000')
    elif urgency == 'MODERE':
        weight, spread_cap = Decimal('0.12'), Decimal('15000')
    else:
        weight, spread_cap = Decimal('0.10'), Decimal('12000')

    complexity_part = min(spread * weight, spread_cap)
    return _round_500(plancher + complexity_part)


def _reservation_price_cap(service: Dict[str, Any], service_id: str) -> Decimal:
    """Soft ceiling to prevent extreme catalog plafonds from leaking to reservation UX."""
    category = str(service.get('category') or '')
    urgency = str(service.get('urgence') or '').upper()
    if category == 'diagnosis' and service_id != 'diagnostic_obd':
        return Decimal('65000')
    if category == 'diagnosis':
        return Decimal('30000')
    if category in ('scheduled_maintenance', 'preventive_maintenance'):
        return Decimal('50000')
    if urgency == 'CRITIQUE':
        return Decimal('95000')
    if urgency == 'MODERE':
        return Decimal('75000')
    return Decimal('60000')


def infer_zone_deplacement(reservation) -> tuple[str, Optional[float]]:
    """Infer displacement zone automatically from technician/client GPS distance.

    No driver input is required. The mobile app should not ask for 'zone centrale' /
    'zone éloignée'. If GPS is unavailable, no displacement surcharge is applied.
    """
    try:
        tech_location = reservation.technician.user.location if reservation.technician else None
        client_location = reservation.location
        if not tech_location or not client_location:
            return 'aucune', None
        distance_km = float(tech_location.distance(client_location) * 111)
        if distance_km <= 8:
            return 'centrale', round(distance_km, 2)
        return 'eloignee', round(distance_km, 2)
    except Exception:
        return 'aucune', None


def resolve_vehicle_pricing(brand: str, model: str, fallback: Optional[str] = None) -> tuple[str, Decimal]:
    """Resolve vehicle gamme and coefficient from DB catalog first, then default algorithm."""
    try:
        from apps.vehicles.models import VehicleCatalog
        item = VehicleCatalog.objects.filter(
            brand__iexact=(brand or '').strip(),
            model__iexact=(model or '').strip(),
            is_active=True,
        ).first()
        if item:
            coeff = Decimal(str(item.coefficient or GAMME_COEFFICIENTS.get(item.gamme, Decimal('1.0'))))
            return item.gamme, coeff
    except Exception:
        pass
    gamme = DEFAULT_VEHICLES.get(_key(brand, model), fallback or 'standard')
    return gamme, GAMME_COEFFICIENTS.get(gamme, Decimal('1.0'))


def resolve_vehicle_gamme(brand: str, model: str, fallback: Optional[str] = None) -> str:
    return resolve_vehicle_pricing(brand, model, fallback)[0]


def list_pricing_services(category: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = []
    for service_id, data in SERVICES.items():
        if category and data.get('category') != category:
            continue
        rows.append({'id': service_id, **data})
    return sorted(rows, key=lambda x: (str(x.get('category')), str(x.get('label'))))


def calculate_quote(*, brand: str, model: str, year: int, service_id: str, urgency: bool = False,
                    intervention_datetime: Optional[datetime] = None, zone_deplacement: str = 'aucune',
                    pieces_oem: bool = False, technician_rating: float = 4.0, first_driver: bool = False,
                    gamme_override: Optional[str] = None) -> Dict[str, Any]:
    if service_id not in SERVICES:
        raise ValueError(f"Service '{service_id}' non catalogué")

    service = SERVICES[service_id]
    gamme, raw_coeff = resolve_vehicle_pricing(brand, model, gamme_override)
    coeff = _soft_vehicle_coefficient(raw_coeff)

    dt = intervention_datetime or timezone.localtime()
    if timezone.is_aware(dt):
        local_dt = timezone.localtime(dt)
    else:
        local_dt = dt

    pct = Decimal('0')
    forfait = Decimal('0')
    factors: List[Dict[str, Any]] = []

    def add_pct(code: str, label: str, value: str):
        nonlocal pct
        pct += Decimal(value)
        factors.append({'code': code, 'label': label, 'type': 'percentage', 'value': str(Decimal(value))})

    def add_fixed(code: str, label: str, value: int):
        nonlocal forfait
        forfait += Decimal(value)
        factors.append({'code': code, 'label': label, 'type': 'fixed', 'value': value})

    if urgency:
        add_pct('urgence', 'Urgence +20%', '0.20')
    if local_dt.hour >= 20 or local_dt.hour < 7:
        add_pct('nuit', 'Intervention de nuit +25%', '0.25')
    if local_dt.weekday() in (5, 6):
        add_pct('weekend', 'Week-end +15%', '0.15')
    current_year = timezone.localdate().year
    if (current_year - int(year or current_year)) > 15:
        add_pct('anciennete', 'Véhicule de plus de 15 ans +15%', '0.15')
    if pieces_oem:
        add_pct('oem', 'Pièces OEM +35%', '0.35')

    # La note ne baisse jamais automatiquement un prix. Un bonus est appliqué aux experts certifiés.
    try:
        rating = Decimal(str(technician_rating or 0))
        if rating >= Decimal('4.5'):
            add_pct('technicien_expert', 'Technicien expert certifié +5%', '0.05')
    except Exception:
        pass

    if zone_deplacement == 'centrale':
        add_fixed('deplacement_central', 'Déplacement automatique courte distance', 2500)
    elif zone_deplacement == 'eloignee':
        add_fixed('deplacement_eloigne', 'Déplacement automatique longue distance', 5000)

    if first_driver:
        factors.append({'code': 'premier_conducteur', 'label': 'Premier conducteur : diagnostic offert selon conditions', 'type': 'info', 'value': 0})

    plancher = Decimal(str(service['plancher']))
    plafond = Decimal(str(service['plafond']))
    base_reference = _service_reference_price(service)

    # Premier conducteur: le diagnostic est offert; les éventuels frais de déplacement
    # restent inclus automatiquement dans le prix exact.
    service_category = str(service.get('category') or '')
    if first_driver and service_category == 'diagnosis':
        base_reference = Decimal('0')
        factors.append({'code': 'diagnostic_offert', 'label': 'Diagnostic offert au premier conducteur', 'type': 'discount', 'value': '100%'})

    gross_without_displacement = base_reference * coeff * (Decimal('1') + pct)
    capped_without_displacement = min(gross_without_displacement, _reservation_price_cap(service, service_id))
    gross_exact = capped_without_displacement + forfait
    montant_exact = _round_500(max(gross_exact, Decimal('0')))
    commission_rate = Decimal('0.12') if urgency else Decimal('0.10')

    commission_exact = _round_500(montant_exact * commission_rate)
    technicien_exact = montant_exact - commission_exact

    return {
        'pricing_version': PRICING_VERSION,
        'display_mode': 'exact',
        'vehicle': {'brand': brand, 'model': model, 'year': year, 'gamme': gamme, 'coefficient': float(coeff), 'raw_coefficient': float(raw_coeff)},
        'service': {
            'id': service_id,
            'label': service.get('label'),
            'category': service.get('category'),
            'niveau_urgence': service.get('urgence'),
            'plancher_reference': int(plancher),
            'plafond_reference': int(plafond),
            'base_reference': int(base_reference),
            'reservation_price_cap': int(_reservation_price_cap(service, service_id)),
        },
        'factors': factors,
        'percentage_total': float(pct),
        'fixed_total': int(forfait),
        'prix_exact': int(montant_exact),
        'client_amount': int(montant_exact),
        'technicien_amount': int(technicien_exact),
        'commission_amount': int(commission_exact),
        'taux_commission': f'{int(commission_rate * 100)}%',
        # Backward-compatible keys kept equal to the exact amount. The UI must no longer
        # display them as a range.
        'fourchette_min': int(montant_exact),
        'fourchette_max': int(montant_exact),
        'technicien_min': int(technicien_exact),
        'technicien_max': int(technicien_exact),
        'commission_min': int(commission_exact),
        'commission_max': int(commission_exact),
    }


def calculate_reservation_quote(reservation, *, pieces_oem: bool = False, zone_deplacement: Optional[str] = None) -> Dict[str, Any]:
    vehicle = reservation.vehicle
    service_id = reservation.intervention_type or reservation.service_type or 'diagnostic_obd'
    if service_id not in SERVICES:
        fallback_by_type = {
            'scheduled_maintenance': 'vidange',
            'preventive_maintenance': 'filtre_air',
            'specific_repair': 'plaquettes_avant',
            'diagnosis': 'diagnostic_obd',
            'emergency': 'batterie',
        }
        service_id = fallback_by_type.get(reservation.service_type, 'diagnostic_obd')
    rating = float(getattr(reservation.technician, 'rating', 4.0) or 4.0) if reservation.technician else 4.0
    inferred_zone, distance_km = infer_zone_deplacement(reservation)
    selected_zone = zone_deplacement or inferred_zone
    try:
        from apps.reservations.models import Reservation
        first_driver = not Reservation.objects.filter(client=reservation.client).exclude(pk=reservation.pk).exists()
    except Exception:
        first_driver = False

    quote = calculate_quote(
        brand=getattr(vehicle, 'brand', '') if vehicle else '',
        model=getattr(vehicle, 'model', '') if vehicle else '',
        year=getattr(vehicle, 'year', timezone.localdate().year) if vehicle else timezone.localdate().year,
        service_id=service_id,
        urgency=reservation.is_emergency,
        intervention_datetime=reservation.date,
        zone_deplacement=selected_zone,
        pieces_oem=pieces_oem,
        technician_rating=rating,
        first_driver=first_driver,
    )
    quote['distance_km'] = distance_km
    quote['zone_deplacement'] = selected_zone
    return quote
