"""
Migration initiale pour apps.admin_panel
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Signalement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contenu', models.CharField(max_length=255, verbose_name='Sujet / Utilisateur signalé')),
                ('signale_par_nom', models.CharField(blank=True, max_length=255, verbose_name='Nom signalant (cache)')),
                ('raison', models.TextField(verbose_name='Raison du signalement')),
                ('type', models.CharField(
                    choices=[
                        ('rendez_vous', 'Non-respect du rendez-vous'),
                        ('comportement', 'Comportement inapproprié'),
                        ('fraude', 'Tentative de fraude'),
                        ('autre', 'Autre'),
                    ],
                    default='autre',
                    max_length=20,
                )),
                ('status', models.CharField(
                    choices=[
                        ('en_attente', 'En attente'),
                        ('traite', 'Traité'),
                        ('rejete', 'Rejeté'),
                    ],
                    default='en_attente',
                    max_length=20,
                )),
                ('nombre_fois_signale', models.IntegerField(default=1)),
                ('note_admin', models.TextField(blank=True, verbose_name="Note de l'administrateur")),
                ('traite_le', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('signale_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='signalements_emis',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Signalé par',
                )),
                ('utilisateur_vise', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='signalements_recus',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Utilisateur visé',
                )),
                ('traite_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='signalements_traites',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Traité par',
                )),
            ],
            options={
                'verbose_name': 'Signalement',
                'verbose_name_plural': 'Signalements',
                'db_table': 'signalements',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(
                    choices=[
                        ('moderation', 'Modération'),
                        ('utilisateurs', 'Utilisateurs'),
                        ('statistique', 'Statistique'),
                        ('vente', 'Vente'),
                        ('vehicule', 'Véhicule'),
                    ],
                    default='moderation',
                    max_length=20,
                )),
                ('titre', models.CharField(max_length=255)),
                ('message', models.TextField()),
                ('lu', models.BooleanField(default=False)),
                ('lu_le', models.DateTimeField(blank=True, null=True)),
                ('lien_type', models.CharField(blank=True, max_length=50)),
                ('lien_id', models.CharField(blank=True, max_length=50)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('destinataire', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='admin_notifications',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Destinataire',
                )),
            ],
            options={
                'verbose_name': 'Notification admin',
                'verbose_name_plural': 'Notifications admin',
                'db_table': 'admin_notifications',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='signalement',
            index=models.Index(fields=['status', 'type'], name='signalement_status_type_idx'),
        ),
        migrations.AddIndex(
            model_name='signalement',
            index=models.Index(fields=['utilisateur_vise'], name='signalement_user_vise_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['destinataire', 'lu'], name='notif_destinataire_lu_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['type'], name='notif_type_idx'),
        ),
    ]