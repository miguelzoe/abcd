# Generated manually
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('reservations', '0003_chatconversation_chatmessage_diagnostic_invoice_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('deposit', 'Dépôt'), ('final', 'Frais intervention')], max_length=10)),
                ('provider', models.CharField(choices=[('momo', 'MTN Mobile Money'), ('om', 'Orange Money')], max_length=10)),
                ('phone_number', models.CharField(max_length=32)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('status', models.CharField(choices=[('pending', 'En attente'), ('confirmed', 'Confirmé'), ('failed', 'Échoué'), ('cancelled', 'Annulé')], default='pending', max_length=10)),
                ('external_reference', models.CharField(blank=True, default='', max_length=64)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('reservation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='reservations.reservation')),
            ],
            options={
                'db_table': 'payment_transactions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='paymenttransaction',
            index=models.Index(fields=['reservation', 'kind', 'status'], name='payment_tr_reservat_67a6c8_idx'),
        ),
        migrations.AddIndex(
            model_name='paymenttransaction',
            index=models.Index(fields=['status', 'created_at'], name='payment_tr_status__71f5be_idx'),
        ),
    ]
