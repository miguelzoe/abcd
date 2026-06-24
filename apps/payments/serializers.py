from rest_framework import serializers
from .models import PaymentTransaction


class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'reservation', 'kind', 'provider', 'phone_number', 'amount',
            'status', 'external_reference', 'metadata',
            'created_at', 'updated_at', 'confirmed_at'
        ]
        read_only_fields = ['id', 'status', 'external_reference', 'metadata', 'created_at', 'updated_at', 'confirmed_at']


class PaymentInitiateSerializer(serializers.Serializer):
    reservation_id = serializers.IntegerField()
    kind = serializers.ChoiceField(choices=['deposit', 'final'])
    provider = serializers.ChoiceField(choices=['momo', 'om', 'wave_ci', 'orange_ci', 'moov_bf', 'airtel_ga', 'card', 'cash'])
    country = serializers.CharField(max_length=3, required=False, allow_blank=True, default='CM')
    phone_number = serializers.CharField(max_length=32)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    PROVIDER_COUNTRIES = {
        'momo': 'CM',
        'om': 'CM',
        'wave_ci': 'CI',
        'orange_ci': 'CI',
        'moov_bf': 'BF',
        'airtel_ga': 'GA',
        'card': 'INT',
        'cash': 'INT',
    }

    PROVIDER_LABELS = {
        'momo': 'MTN Mobile Money',
        'om': 'Orange Money',
        'wave_ci': 'Wave Côte d’Ivoire',
        'orange_ci': 'Orange Money Côte d’Ivoire',
        'moov_bf': 'Moov Money Burkina Faso',
        'airtel_ga': 'Airtel Money Gabon',
        'card': 'Carte bancaire',
        'cash': 'Paiement en main propre',
    }

    def validate(self, data):
        provider = data.get('provider')
        phone = (data.get('phone_number') or '').strip().replace(' ', '').replace('-', '')
        country = (data.get('country') or self.PROVIDER_COUNTRIES.get(provider) or 'INT').upper()

        if provider == 'cash':
            data['phone_number'] = phone or 'CASH'
            data['country'] = country
            return data

        if provider == 'card':
            data['phone_number'] = phone or 'CARD'
            data['country'] = country
            return data

        if not phone.startswith('+'):
            prefixes = {
                'CM': '+237',
                'CI': '+225',
                'BF': '+226',
                'GA': '+241',
                'FR': '+33',
            }
            prefix = prefixes.get(country)
            if prefix and phone:
                phone = f"{prefix}{phone.lstrip('0')}"

        if not phone.startswith('+') or len(phone) < 8:
            raise serializers.ValidationError({
                'phone_number': "Veuillez saisir un numéro au format international, par exemple +237699000000."
            })

        data['phone_number'] = phone
        data['country'] = country
        return data


class PaymentConfirmSerializer(serializers.Serializer):
    otp_code = serializers.CharField(max_length=10, required=False, allow_blank=True)
