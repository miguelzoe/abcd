# Generated manually for marketplace article types
from django.db import migrations, models
import django.utils.timezone


def seed_types(apps, schema_editor):
    ArticleType = apps.get_model('marketplace', 'MarketplaceArticleType')
    data = [
        ('pieces-detachees', 'Pièces détachées', 'piece'),
        ('vehicules-vente', 'Véhicules à vendre', 'vehicle_sale'),
        ('vehicules-location', 'Véhicules à louer', 'vehicle_rental'),
        ('accessoires', 'Accessoires', 'piece'),
    ]
    for code, label, kind in data:
        ArticleType.objects.update_or_create(code=code, defaults={'label': label, 'kind': kind, 'is_active': True})


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0002_avis_alter_commande_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='MarketplaceArticleType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.SlugField(max_length=60, unique=True)),
                ('label', models.CharField(max_length=120)),
                ('kind', models.CharField(choices=[('piece', 'Pièce détachée'), ('vehicle_sale', 'Véhicule à vendre'), ('vehicle_rental', 'Véhicule à louer'), ('service', 'Service'), ('other', 'Autre')], default='piece', max_length=30)),
                ('description', models.TextField(blank=True, default='')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': "Type d'article marketplace",
                'verbose_name_plural': "Types d'articles marketplace",
                'db_table': 'marketplace_article_types',
                'ordering': ['kind', 'label'],
            },
        ),
        migrations.RunPython(seed_types, migrations.RunPython.noop),
    ]
