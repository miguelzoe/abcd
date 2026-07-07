# Generated manually for Cartronic profile-photo persistence.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0010_store_technician_documents_in_db'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='profile_photo',
            field=models.ImageField(blank=True, null=True, upload_to='users/profile_photos/'),
        ),
        migrations.AddField(
            model_name='user',
            name='profile_photo_data',
            field=models.BinaryField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='profile_photo_content_type',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='user',
            name='profile_photo_filename',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
