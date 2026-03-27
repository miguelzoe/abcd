from django.urls import path
from .views import PaymentInitiate, PaymentConfirm, ReservationPaymentSummary

urlpatterns = [
    path('payments/initiate/', PaymentInitiate.as_view(), name='payment-initiate'),
    path('payments/confirm/<int:payment_id>/', PaymentConfirm.as_view(), name='payment-confirm'),
    path('payments/<int:payment_id>/confirm/', PaymentConfirm.as_view(), name='payment-confirm-alias'),
    path('payments/reservation/<int:reservation_id>/', ReservationPaymentSummary.as_view(), name='payment-reservation-summary'),
    path('payments/reservations/<int:reservation_id>/summary/', ReservationPaymentSummary.as_view(), name='payment-reservation-summary-alias'),
]
