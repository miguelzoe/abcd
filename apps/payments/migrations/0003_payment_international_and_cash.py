# Generated manually for Cartronic test corrections
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0002_rename_payment_tr_reservat_67a6c8_idx_payment_tra_reserva_ca8b2b_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymenttransaction',
            name='provider',
            field=models.CharField(choices=[('momo', 'MTN Mobile Money'), ('om', 'Orange Money'), ('wave_ci', 'Wave Côte d’Ivoire'), ('orange_ci', 'Orange Money Côte d’Ivoire'), ('moov_bf', 'Moov Money Burkina Faso'), ('airtel_ga', 'Airtel Money Gabon'), ('card', 'Carte bancaire'), ('cash', 'Paiement en main propre')], max_length=10),
        ),
    ]
