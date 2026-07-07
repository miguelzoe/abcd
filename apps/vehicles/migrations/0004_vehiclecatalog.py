# Generated manually for Cartronic pricing catalog
from django.db import migrations, models
import django.db.models.deletion


def seed_catalog(apps, schema_editor):
    VehicleCatalog = apps.get_model('vehicles', 'VehicleCatalog')
    data = [
        ('toyota','corolla','economique',1.0),('toyota','matrix','economique',1.0),('toyota','camry','economique',1.0),('toyota','auris','economique',1.0),
        ('honda','civic','economique',1.0),('honda','jazz','economique',1.0),('nissan','almera','economique',1.0),('peugeot','406','economique',1.0),('mazda','323','economique',1.0),
        ('toyota','avensis','standard',1.3),('toyota','yaris','standard',1.3),('toyota','venza','standard',1.3),('honda','accord','standard',1.3),('hyundai','elantra','standard',1.3),('kia','cerato','standard',1.3),
        ('toyota','rav4','suv',1.6),('toyota','fortuner','suv',1.6),('honda','crv','suv',1.6),('kia','sportage','suv',1.6),('hyundai','tucson','suv',1.6),('mercedes','ml','suv',1.6),
        ('toyota','prado','4x4',1.8),('toyota','hilux','4x4',1.8),('toyota','landcruiser','4x4',1.8),('mitsubishi','l200','4x4',1.8),('nissan','navara','4x4',1.8),
        ('toyota','hiace','utilitaire',2.0),('toyota','coaster','utilitaire',2.0),('mitsubishi','l300','utilitaire',2.0),
        ('lexus','rx350','premium',2.5),('mercedes','classe_e','premium',2.5),('bmw','serie5','premium',2.5),('audi','q7','premium',2.5),
    ]
    for brand, model, gamme, coeff in data:
        VehicleCatalog.objects.update_or_create(
            brand=brand, model=model,
            defaults={'gamme': gamme, 'coefficient': coeff, 'is_active': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0003_remove_vehicle_vehicles_marque_472948_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='VehicleCatalog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('brand', models.CharField(max_length=100, verbose_name='Marque')),
                ('model', models.CharField(max_length=100, verbose_name='Modèle')),
                ('gamme', models.CharField(choices=[('economique', 'Économique'), ('standard', 'Standard'), ('suv', 'SUV'), ('4x4', '4x4'), ('utilitaire', 'Utilitaire'), ('premium', 'Premium')], default='standard', max_length=30)),
                ('coefficient', models.DecimalField(decimal_places=2, default=1.3, max_digits=4)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Type de véhicule tarifaire',
                'verbose_name_plural': 'Types de véhicules tarifaires',
                'db_table': 'vehicle_catalog',
                'ordering': ['brand', 'model'],
                'unique_together': {('brand', 'model')},
            },
        ),
        migrations.AddIndex(
            model_name='vehiclecatalog',
            index=models.Index(fields=['brand', 'model'], name='vehicle_cata_brand_1dd95a_idx'),
        ),
        migrations.AddIndex(
            model_name='vehiclecatalog',
            index=models.Index(fields=['gamme', 'is_active'], name='vehicle_cata_gamme_8bee9e_idx'),
        ),
        migrations.RunPython(seed_catalog, migrations.RunPython.noop),
    ]
