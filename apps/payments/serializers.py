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
    provider = serializers.ChoiceField(choices=['momo', 'om'])
    phone_number = serializers.CharField(max_length=32)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    # Préfixes valides par opérateur (Cameroun)
    PROVIDER_PREFIXES = {
        'momo': ['650', '651', '652', '653', '654', '670', '671', '672', '673', '674', '675', '676', '677', '678', '679'],
        'om':   ['655', '656', '657', '658', '659', '690', '691', '692', '693', '694', '695', '696', '697', '698', '699'],
    }

    def validate(self, data):
        phone = data.get('phone_number', '').strip().replace(' ', '').replace('-', '')
        provider = data.get('provider')

        # Normaliser : accepte +237XXXXXXXXX ou 6XXXXXXXX
        if phone.startswith('+237'):
            local = phone[4:]
        elif phone.startswith('237'):
            local = phone[3:]
        else:
            local = phone

        if len(local) != 9 or not local.isdigit():
            raise serializers.ValidationError({
                'phone_number': "Format invalide. Utilisez +237XXXXXXXXX ou 6XXXXXXXX (9 chiffres locaux)."
            })

        prefix3 = local[:3]
        allowed = self.PROVIDER_PREFIXES.get(provider, [])
        if allowed and prefix3 not in allowed:
            label = 'MTN Mobile Money' if provider == 'momo' else 'Orange Money'
            raise serializers.ValidationError({
                'phone_number': f"Ce numéro ne correspond pas à un abonné {label}."
            })

        data['phone_number'] = f"+237{local}"
        return data


class PaymentConfirmSerializer(serializers.Serializer):
    otp_code = serializers.CharField(max_length=10, required=False, allow_blank=True)
