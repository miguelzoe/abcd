# Generated for Cartronic VoIP integration
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reservations', '0003_chatconversation_chatmessage_diagnostic_invoice_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='VoiceCallSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('status', models.CharField(choices=[('ringing', 'Sonnerie'), ('accepted', 'Accepté'), ('rejected', 'Refusé'), ('missed', 'Manqué'), ('ended', 'Terminé'), ('cancelled', 'Annulé'), ('failed', 'Échec')], default='ringing', max_length=20)),
                ('started_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('answered_at', models.DateTimeField(blank=True, null=True)),
                ('ended_at', models.DateTimeField(blank=True, null=True)),
                ('duration_seconds', models.PositiveIntegerField(default=0)),
                ('end_reason', models.CharField(blank=True, default='', max_length=120)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('callee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='incoming_voice_calls', to=settings.AUTH_USER_MODEL)),
                ('caller', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outgoing_voice_calls', to=settings.AUTH_USER_MODEL)),
                ('reservation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='voice_calls', to='reservations.reservation')),
            ],
            options={
                'verbose_name': 'Session appel vocal',
                'verbose_name_plural': 'Sessions appels vocaux',
                'db_table': 'voice_call_sessions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='VoiceCallSignal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('signal_type', models.CharField(choices=[('offer', 'Offer SDP'), ('answer', 'Answer SDP'), ('ice-candidate', 'ICE candidate'), ('ringing', 'Sonnerie'), ('accepted', 'Accepté'), ('rejected', 'Refusé'), ('ended', 'Terminé'), ('failed', 'Échec'), ('mute-state', 'État micro')], max_length=40)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='voice_signals', to=settings.AUTH_USER_MODEL)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='signals', to='voice_calls.voicecallsession')),
            ],
            options={
                'verbose_name': 'Signal appel vocal',
                'verbose_name_plural': 'Signaux appels vocaux',
                'db_table': 'voice_call_signals',
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(model_name='voicecallsession', index=models.Index(fields=['caller', 'status', 'created_at'], name='voice_call__caller__3f3c24_idx')),
        migrations.AddIndex(model_name='voicecallsession', index=models.Index(fields=['callee', 'status', 'created_at'], name='voice_call__callee__9c2a14_idx')),
        migrations.AddIndex(model_name='voicecallsession', index=models.Index(fields=['reservation', 'created_at'], name='voice_call__reserva_8470b0_idx')),
        migrations.AddIndex(model_name='voicecallsignal', index=models.Index(fields=['session', 'created_at'], name='voice_call__session_46674c_idx')),
        migrations.AddIndex(model_name='voicecallsignal', index=models.Index(fields=['sender', 'signal_type'], name='voice_call__sender__3a9225_idx')),
    ]
