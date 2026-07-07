from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reservations', '0004_pricing_details'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReservationReminder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reminder_type', models.CharField(choices=[('day_morning', 'Rappel du matin'), ('one_hour_before', 'Rappel 1h avant')], max_length=30)),
                ('scheduled_for', models.DateTimeField()),
                ('title', models.CharField(max_length=160)),
                ('body', models.TextField()),
                ('data', models.JSONField(blank=True, default=dict)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reservation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reminders', to='reservations.reservation')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reservation_reminders', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'reservation_reminders',
                'ordering': ['scheduled_for'],
                'unique_together': {('reservation', 'user', 'reminder_type')},
            },
        ),
        migrations.AddIndex(
            model_name='reservationreminder',
            index=models.Index(fields=['user', 'scheduled_for'], name='reservation_user_id_348b61_idx'),
        ),
        migrations.AddIndex(
            model_name='reservationreminder',
            index=models.Index(fields=['sent_at', 'scheduled_for'], name='reservation_sent_at_9db08c_idx'),
        ),
        migrations.AddIndex(
            model_name='reservationreminder',
            index=models.Index(fields=['reservation', 'reminder_type'], name='reservation_reserva_669a5e_idx'),
        ),
    ]
