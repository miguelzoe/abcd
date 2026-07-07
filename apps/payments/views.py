from decimal import Decimal
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reservations.models import Reservation, ChatConversation
from apps.users.models import Notification
from apps.users.services import send_expo_push_to_user

from .models import PaymentTransaction
from .serializers import PaymentInitiateSerializer, PaymentConfirmSerializer, PaymentTransactionSerializer


# Paiements fictifs: le montant est désormais le prix exact calculé par l'algorithme Cartronic.
PLATFORM_FEE = Decimal('0.00')


def _notify(user, title: str, body: str, data=None):
    notif = Notification.objects.create(user=user, title=title, body=body, data=data or {})
    send_expo_push_to_user(user, title=title, body=body, data=data or {})
    return notif


def _ensure_chat(reservation: Reservation):
    if reservation.technician_id is None:
        return None
    convo, _ = ChatConversation.objects.get_or_create(reservation=reservation)
    return convo


class ReservationPaymentSummary(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, reservation_id: int):
        try:
            reservation = Reservation.objects.select_related('client__user', 'technician__user').get(id=reservation_id)
        except Reservation.DoesNotExist:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        u = request.user
        if u.user_type == 'client':
            if reservation.client.user_id != u.id:
                return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        elif u.user_type == 'technician':
            if reservation.technician is None or reservation.technician.user_id != u.id:
                return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        deposit = PaymentTransaction.objects.filter(reservation=reservation, kind='deposit').order_by('-created_at').first()
        final = PaymentTransaction.objects.filter(reservation=reservation, kind='final').order_by('-created_at').first()

        return Response({
            'reservation_id': reservation.id,
            'deposit': PaymentTransactionSerializer(deposit).data if deposit else None,
            'final': PaymentTransactionSerializer(final).data if final else None,
        })


class PaymentInitiate(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        s = PaymentInitiateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        try:
            reservation = Reservation.objects.select_related('client__user', 'technician__user').get(id=data['reservation_id'])
        except Reservation.DoesNotExist:
            return Response({'detail': 'Reservation not found'}, status=status.HTTP_404_NOT_FOUND)

        if request.user.user_type != 'client' or reservation.client.user_id != request.user.id:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        kind = data['kind']
        amount = data['amount']

        # Le client ne paie plus un forfait déplacement fixe de 2 000 FCFA.
        # Si le mobile n'envoie pas de montant, ou envoie 0, on reprend le prix exact
        # enregistré sur la réservation par le moteur de tarification.
        exact_amount = Decimal(str(reservation.price or 0))
        if amount <= Decimal('0') and exact_amount > 0:
            amount = exact_amount
        if kind == 'deposit' and exact_amount > 0:
            amount = exact_amount
        if amount <= Decimal('0'):
            return Response({'detail': 'Montant de réservation invalide ou non calculé.'}, status=status.HTTP_400_BAD_REQUEST)

        # Remplace toute ancienne transaction pending du même type
        PaymentTransaction.objects.filter(reservation=reservation, kind=kind, status='pending').update(status='cancelled')

        initial_status = 'confirmed' if data['provider'] == 'cash' else 'pending'
        tx = PaymentTransaction.objects.create(
            reservation=reservation,
            kind=kind,
            provider=data['provider'],
            phone_number=data['phone_number'],
            amount=amount,
            status=initial_status,
            external_reference=f"PM-{reservation.id}-{kind}-{int(timezone.now().timestamp())}",
            metadata={
                'mode': 'cash' if data['provider'] == 'cash' else 'mock_payment',
                'mock_mode': True,
                'client_can_confirm_in_app': True,
                'step': 'prompt_sent',
                'provider_label': PaymentInitiateSerializer.PROVIDER_LABELS.get(data['provider'], data['provider']),
                'country': data.get('country', ''),
                'prompt_message': f"Confirmez le paiement fictif Cartronic de {amount} FCFA sur le numéro {data['phone_number']}",
            },
        )

        if data['provider'] == 'cash':
            tx.confirmed_at = timezone.now()
            tx.save(update_fields=['confirmed_at', 'updated_at'])
            body = f"Paiement en main propre enregistré pour {amount} FCFA."
        else:
            body = f"Demande de paiement {tx.metadata.get('provider_label')} créée pour {amount} FCFA sur le numéro {data['phone_number']}."
        _notify(
            reservation.client.user,
            'Simulation de paiement prête',
            body,
            data={
                'type': 'payment_prompt_sent',
                'kind': kind,
                'reservation_id': reservation.id,
                'payment_id': tx.id,
                'amount': float(amount),
            },
        )

        return Response(PaymentTransactionSerializer(tx).data, status=status.HTTP_201_CREATED)


class PaymentConfirm(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, payment_id: int):
        s = PaymentConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        try:
            tx = PaymentTransaction.objects.select_related('reservation__client__user', 'reservation__technician__user').get(id=payment_id)
        except PaymentTransaction.DoesNotExist:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        reservation = tx.reservation

        if request.user.user_type != 'client' or reservation.client.user_id != request.user.id:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        if tx.status == 'confirmed':
            return Response(PaymentTransactionSerializer(tx).data)

        tx.status = 'confirmed'
        tx.confirmed_at = timezone.now()
        tx.metadata = {**(tx.metadata or {}), 'step': 'confirmed', 'otp_code': s.validated_data.get('otp_code', ''), 'confirmed_in_app': True}
        tx.save(update_fields=['status', 'confirmed_at', 'metadata', 'updated_at'])

        if tx.kind == 'deposit':
            _notify(
                reservation.client.user,
                'Réservation payée',
                'Le paiement exact de la réservation a été confirmé. Le technicien est maintenant autorisé à démarrer le trajet.',
                data={'type': 'payment_confirmed', 'kind': 'deposit', 'reservation_id': reservation.id},
            )
            if reservation.technician_id:
                _ensure_chat(reservation)
                tech_user = reservation.technician.user
                _notify(
                    tech_user,
                    'Paiement confirmé',
                    'Le montant exact de la réservation a été payé. Vous pouvez démarrer le trajet vers le client.',
                    data={'type': 'payment_confirmed', 'kind': 'deposit', 'reservation_id': reservation.id},
                )

        if tx.kind == 'final':
            if reservation.technician_id:
                tech_user = reservation.technician.user
                _notify(
                    tech_user,
                    'Paiement confirmé',
                    'Le client a confirmé le paiement de la facture. Vous pouvez poursuivre et terminer la mission.',
                    data={'type': 'payment_confirmed', 'kind': 'final', 'reservation_id': reservation.id}
                )
            _notify(
                reservation.client.user,
                'Facture payée',
                'Votre paiement a été confirmé. Le technicien a été notifié automatiquement.',
                data={'type': 'payment_confirmed', 'kind': 'final', 'reservation_id': reservation.id}
            )

        return Response(PaymentTransactionSerializer(tx).data)
