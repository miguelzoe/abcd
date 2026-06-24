# Generated for Cartronic V14 reminder timing cleanup

from django.db import migrations, models


def remove_legacy_one_hour_reminders(apps, schema_editor):
    ReservationReminder = apps.get_model('reservations', 'ReservationReminder')
    ReservationReminder.objects.filter(reminder_type='one_hour_before').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0005_reservation_reminder'),
    ]

    operations = [
        migrations.RunPython(remove_legacy_one_hour_reminders, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='reservationreminder',
            name='reminder_type',
            field=models.CharField(
                max_length=30,
                choices=[
                    ('day_before', 'Rappel la veille'),
                    ('day_morning', 'Rappel du jour à 7h'),
                ],
            ),
        ),
    ]
