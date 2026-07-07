from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_pushtoken_notification'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='password_changed_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='user',
            name='password_expiry_notified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='technician',
            name='approval_status',
            field=models.CharField(
                choices=[('pending', 'En attente'), ('approved', 'Approuvé'), ('rejected', 'Refusé')],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='technician',
            name='rejection_reason',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='techniciandocument',
            name='validation_status',
            field=models.CharField(
                choices=[('non_verifie', 'Non vérifié'), ('valide', 'Valide'), ('invalide', 'Invalide')],
                default='non_verifie',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='techniciandocument',
            name='validation_comment',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddIndex(
            model_name='technician',
            index=models.Index(fields=['approval_status'], name='technicians_approva_fusion_idx'),
        ),
    ]
