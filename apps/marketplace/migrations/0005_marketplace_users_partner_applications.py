# Generated manually for marketplace account separation and partner accreditation.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('marketplace', '0004_marketplace_mobile_api'),
        ('users', '0013_marketplace_user_roles_vendor_accreditation'),
    ]

    operations = [
        migrations.CreateModel(
            name='MarketplacePartnerApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('partner_type', models.CharField(choices=[('parts_seller', 'Vendeur de pièces / produits'), ('auto_shop', 'Boutique automobile / location')], max_length=30)),
                ('company_name', models.CharField(max_length=200)),
                ('business_license', models.CharField(blank=True, default='', max_length=120)),
                ('contact_phone', models.CharField(blank=True, default='', max_length=30)),
                ('message', models.TextField(blank=True, default='')),
                ('status', models.CharField(choices=[('pending', 'En attente'), ('approved', 'Approuvée'), ('rejected', 'Refusée')], default='pending', max_length=20)),
                ('rejection_reason', models.TextField(blank=True, default='')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_marketplace_applications', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='marketplace_partner_applications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Demande partenaire marketplace',
                'verbose_name_plural': 'Demandes partenaires marketplace',
                'db_table': 'marketplace_partner_applications',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AlterField(
            model_name='marketplaceorder',
            name='client',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='marketplace_orders', to='users.client'),
        ),
        migrations.AddField(
            model_name='marketplaceorder',
            name='marketplace_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='marketplace_orders', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddIndex(model_name='marketplacepartnerapplication', index=models.Index(fields=['status', 'partner_type'], name='mkt_partner_status_0d7d1e_idx')),
        migrations.AddIndex(model_name='marketplacepartnerapplication', index=models.Index(fields=['user', 'status'], name='mkt_partner_user_9ecb40_idx')),
        migrations.AddIndex(model_name='marketplaceorder', index=models.Index(fields=['marketplace_user', 'status'], name='marketplace_user_s_2d2d5d_idx')),
    ]
