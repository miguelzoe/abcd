# Generated manually for Cartronic test corrections
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_rename_notificatio_user_id_3e4dd6_idx_notificatio_user_id_7336fd_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='technician',
            name='years_experience',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='technician',
            name='profile_photo',
            field=models.ImageField(blank=True, null=True, upload_to='technicians/profile_photos/'),
        ),
    ]
