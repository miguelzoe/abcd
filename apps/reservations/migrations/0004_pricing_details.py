# Generated manually for Cartronic pricing traceability
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0003_chatconversation_chatmessage_diagnostic_invoice_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservation',
            name='pricing_details',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='reservation',
            name='pricing_version',
            field=models.CharField(blank=True, default='', max_length=60),
        ),
    ]
