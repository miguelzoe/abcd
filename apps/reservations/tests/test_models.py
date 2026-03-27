"""
Tests des modèles de réservation : propriétés, transitions de statut, invariants.
"""
import pytest
from django.utils import timezone
from django.contrib.gis.geos import Point
from apps.reservations.models import Reservation, Evaluation
from apps.users.models import Technician


def make_reservation(client_profile, technician_profile=None, status="pending", **kwargs):
    """Helper pour créer une réservation de test."""
    return Reservation.objects.create(
        client=client_profile,
        technician=technician_profile,
        service_type="diagnosis",
        urgency_level="low",
        date=timezone.now(),
        status=status,
        description="Problème moteur",
        location=Point(11.5, 3.8, srid=4326),
        **kwargs,
    )


# ─── Propriétés du modèle ─────────────────────────────────────────────────────

@pytest.mark.django_db
class TestReservationProperties:

    def test_is_emergency_with_emergency_service(self, client_profile):
        r = make_reservation(client_profile, service_type="emergency")
        assert r.is_emergency is True

    def test_is_emergency_with_critical_urgency(self, client_profile):
        r = make_reservation(client_profile, urgency_level="critical")
        assert r.is_emergency is True

    def test_is_emergency_false_for_normal(self, client_profile):
        r = make_reservation(client_profile, service_type="diagnosis", urgency_level="low")
        assert r.is_emergency is False

    def test_is_completed(self, client_profile):
        r = make_reservation(client_profile, status="completed")
        assert r.is_completed is True
        assert r.is_cancelled is False

    def test_is_cancelled(self, client_profile):
        r = make_reservation(client_profile, status="cancelled")
        assert r.is_cancelled is True
        assert r.is_completed is False

    def test_can_be_cancelled_when_pending(self, client_profile):
        r = make_reservation(client_profile, status="pending")
        assert r.can_be_cancelled is True

    def test_can_be_cancelled_when_confirmed(self, client_profile):
        r = make_reservation(client_profile, status="confirmed")
        assert r.can_be_cancelled is True

    def test_cannot_be_cancelled_when_in_progress(self, client_profile):
        r = make_reservation(client_profile, status="in_progress")
        assert r.can_be_cancelled is False

    def test_cannot_be_cancelled_when_completed(self, client_profile):
        r = make_reservation(client_profile, status="completed")
        assert r.can_be_cancelled is False

    def test_requires_client_approval(self, client_profile):
        r = make_reservation(client_profile, status="awaiting_client_approval")
        assert r.requires_client_approval is True

    def test_does_not_require_approval_by_default(self, client_profile):
        r = make_reservation(client_profile, status="pending")
        assert r.requires_client_approval is False


# ─── Transitions de statut ────────────────────────────────────────────────────

@pytest.mark.django_db
class TestReservationStatusTransitions:

    def test_status_update_pending_to_confirmed(self, client_profile):
        r = make_reservation(client_profile, status="pending")
        r.status = "confirmed"
        r.save()
        r.refresh_from_db()
        assert r.status == "confirmed"

    def test_cancellation_with_reason(self, client_profile, client_user):
        r = make_reservation(client_profile, status="pending")
        r.status = "cancelled"
        r.cancelled_at = timezone.now()
        r.cancelled_by = client_user
        r.cancellation_reason = "Changement de plan"
        r.save()

        r.refresh_from_db()
        assert r.status == "cancelled"
        assert r.cancellation_reason == "Changement de plan"
        assert r.cancelled_by == client_user


# ─── Evaluation ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestEvaluation:

    def test_create_evaluation(self, client_profile, technician_user):
        tech = technician_user.technician_profile
        r = make_reservation(client_profile, technician_profile=tech, status="completed")

        eval_ = Evaluation.objects.create(
            reservation=r,
            note=5,
            client=client_profile,
            technician=tech,
            response_time_rating=5,
            diagnosis_quality_rating=4,
            communication_rating=5,
            professionalism=5,
            value_for_money=4,
        )

        assert eval_.note == 5
        assert str(eval_) == f"Évaluation 5/5 - {tech.user.username}"

    def test_evaluation_note_bounds(self, client_profile, technician_user):
        """Note doit être entre 1 et 5."""
        from django.core.exceptions import ValidationError
        tech = technician_user.technician_profile
        r = make_reservation(client_profile, technician_profile=tech, status="completed")

        eval_ = Evaluation(
            reservation=r, note=6, client=client_profile, technician=tech,
            response_time_rating=5, diagnosis_quality_rating=4,
            communication_rating=5, professionalism=5, value_for_money=4,
        )
        with pytest.raises(ValidationError):
            eval_.full_clean()

    def test_one_evaluation_per_reservation(self, client_profile, technician_user):
        """Une seule évaluation par réservation (OneToOne)."""
        from django.db import IntegrityError
        tech = technician_user.technician_profile
        r = make_reservation(client_profile, technician_profile=tech, status="completed")

        Evaluation.objects.create(
            reservation=r, note=4, client=client_profile, technician=tech,
            response_time_rating=4, diagnosis_quality_rating=4,
            communication_rating=4, professionalism=4, value_for_money=4,
        )

        with pytest.raises(IntegrityError):
            Evaluation.objects.create(
                reservation=r, note=3, client=client_profile, technician=tech,
                response_time_rating=3, diagnosis_quality_rating=3,
                communication_rating=3, professionalism=3, value_for_money=3,
            )


# ─── Notification de réservation ─────────────────────────────────────────────

@pytest.mark.django_db
class TestReservationNotificationFlags:

    def test_notification_flags_default_false(self, client_profile):
        r = make_reservation(client_profile)
        assert r.client_notified_arrival is False
        assert r.client_notified_diagnosis is False
        assert r.client_notified_completion is False

    def test_set_notification_flags(self, client_profile):
        r = make_reservation(client_profile)
        r.client_notified_arrival = True
        r.save()
        r.refresh_from_db()
        assert r.client_notified_arrival is True
