# Generated manually for marketplace/intervention separation.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0012_rename_techdoc_tech_status_idx_technician__technic_086a40_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='user_type',
            field=models.CharField(
                choices=[
                    ('client', 'Client intervention'),
                    ('technician', 'Technicien intervention'),
                    ('marketplace_customer', 'Client marketplace'),
                    ('vendor', 'Vendeur marketplace'),
                    ('auto_shop', 'Boutique automobile'),
                    ('administrator', 'Administrateur'),
                ],
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='vendor',
            name='partner_type',
            field=models.CharField(
                choices=[('parts_seller', 'Vendeur de pièces / produits'), ('auto_shop', 'Boutique automobile / location')],
                default='parts_seller',
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='vendor',
            name='approval_status',
            field=models.CharField(
                choices=[('pending', 'En attente'), ('approved', 'Approuvé'), ('rejected', 'Refusé')],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='vendor',
            name='rejection_reason',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='vendor',
            name='approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='vendor',
            name='approved_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='approved_marketplace_partners',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterModelOptions(
            name='vendor',
            options={'verbose_name': 'Partenaire marketplace', 'verbose_name_plural': 'Partenaires marketplace'},
        ),
    ]
