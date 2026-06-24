from django.db import migrations


VEHICLE_CATALOG = [
    ('Toyota', 'Corolla', 'economique', '1.00'),
    ('Toyota', 'Matrix', 'economique', '1.00'),
    ('Toyota', 'Camry', 'economique', '1.00'),
    ('Toyota', 'Auris', 'economique', '1.00'),
    ('Honda', 'Civic', 'economique', '1.00'),
    ('Honda', 'Jazz', 'economique', '1.00'),
    ('Nissan', 'Almera', 'economique', '1.00'),
    ('Peugeot', '406', 'economique', '1.00'),
    ('Mazda', '323', 'economique', '1.00'),
    ('Toyota', 'Avensis', 'standard', '1.30'),
    ('Toyota', 'Yaris', 'standard', '1.30'),
    ('Toyota', 'Venza', 'standard', '1.30'),
    ('Honda', 'Accord', 'standard', '1.30'),
    ('Hyundai', 'Elantra', 'standard', '1.30'),
    ('Kia', 'Cerato', 'standard', '1.30'),
    ('Toyota', 'RAV4', 'suv', '1.60'),
    ('Toyota', 'Fortuner', 'suv', '1.60'),
    ('Honda', 'CR-V', 'suv', '1.60'),
    ('Kia', 'Sportage', 'suv', '1.60'),
    ('Hyundai', 'Tucson', 'suv', '1.60'),
    ('Mercedes', 'ML', 'suv', '1.60'),
    ('Toyota', 'Prado', '4x4', '1.80'),
    ('Toyota', 'Hilux', '4x4', '1.80'),
    ('Toyota', 'Land Cruiser', '4x4', '1.80'),
    ('Mitsubishi', 'L200', '4x4', '1.80'),
    ('Nissan', 'Navara', '4x4', '1.80'),
    ('Toyota', 'Hiace', 'utilitaire', '2.00'),
    ('Toyota', 'Coaster', 'utilitaire', '2.00'),
    ('Mitsubishi', 'L300', 'utilitaire', '2.00'),
    ('Lexus', 'RX350', 'premium', '2.50'),
    ('Mercedes', 'Classe E', 'premium', '2.50'),
    ('BMW', 'Série 5', 'premium', '2.50'),
    ('Audi', 'Q7', 'premium', '2.50'),

]


def seed_vehicle_catalog(apps, schema_editor):
    VehicleCatalog = apps.get_model('vehicles', 'VehicleCatalog')
    for brand, model, gamme, coefficient in VEHICLE_CATALOG:
        obj, _ = VehicleCatalog.objects.update_or_create(
            brand=brand,
            model=model,
            defaults={
                'gamme': gamme,
                'coefficient': coefficient,
                'is_active': True,
            },
        )


def unseed_vehicle_catalog(apps, schema_editor):
    VehicleCatalog = apps.get_model('vehicles', 'VehicleCatalog')
    for brand, model, gamme, coefficient in VEHICLE_CATALOG:
        VehicleCatalog.objects.filter(brand=brand, model=model).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0005_rename_vehicle_cata_brand_1dd95a_idx_vehicle_cat_brand_445b0d_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_vehicle_catalog, unseed_vehicle_catalog),
    ]
