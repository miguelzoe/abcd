# Generated for Cartronic: store technician documents directly in PostgreSQL.

from django.db import migrations, models


def migrate_existing_files_to_db(apps, schema_editor):
    """Best-effort migration: copy existing /media files into file_data when present."""
    TechnicianDocument = apps.get_model('users', 'TechnicianDocument')

    for doc in TechnicianDocument.objects.all().iterator():
        update_fields = []

        file_field = getattr(doc, 'file', None)
        file_name = getattr(file_field, 'name', '') if file_field else ''

        if not getattr(doc, 'original_filename', ''):
            doc.original_filename = (file_name.split('/')[-1] if file_name else getattr(doc, 'name', '') or '')
            update_fields.append('original_filename')

        if not getattr(doc, 'name', '') and doc.original_filename:
            doc.name = doc.original_filename
            update_fields.append('name')

        if not getattr(doc, 'content_type', ''):
            lower = (doc.original_filename or file_name or '').lower()
            if lower.endswith('.pdf'):
                doc.content_type = 'application/pdf'
            elif lower.endswith('.png'):
                doc.content_type = 'image/png'
            elif lower.endswith('.webp'):
                doc.content_type = 'image/webp'
            elif lower.endswith('.jpg') or lower.endswith('.jpeg'):
                doc.content_type = 'image/jpeg'
            else:
                doc.content_type = 'application/octet-stream'
            update_fields.append('content_type')

        # Infer document_type from the document label/filename.
        if not getattr(doc, 'document_type', '') or doc.document_type == 'autre':
            lower_label = f"{getattr(doc, 'name', '')} {getattr(doc, 'original_filename', '')}".lower()
            if 'cni' in lower_label or 'identit' in lower_label or 'passeport' in lower_label or 'passport' in lower_label:
                doc.document_type = 'piece_identite'
            elif 'certificat' in lower_label or 'dipl' in lower_label or 'formation' in lower_label:
                doc.document_type = 'certificat'
            elif 'experience' in lower_label or 'expérience' in lower_label or 'travail' in lower_label or 'recommandation' in lower_label:
                doc.document_type = 'experience'
            elif 'assurance' in lower_label:
                doc.document_type = 'assurance'
            else:
                doc.document_type = 'autre'
            update_fields.append('document_type')

        # Copy old local media file into DB if the file still exists.
        if file_field and file_name and not getattr(doc, 'file_data', None):
            try:
                file_field.open('rb')
                content = file_field.read()
                file_field.close()
                if content:
                    doc.file_data = content
                    doc.file_size = len(content)
                    update_fields.extend(['file_data', 'file_size'])
            except Exception:
                # The file may already be gone on Render. Keep metadata only.
                pass

        if update_fields:
            doc.save(update_fields=list(dict.fromkeys(update_fields)))


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_alter_user_managers_alter_technician_approval_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='techniciandocument',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to='technicians/documents/'),
        ),
        migrations.AddField(
            model_name='techniciandocument',
            name='file_data',
            field=models.BinaryField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='techniciandocument',
            name='original_filename',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='techniciandocument',
            name='content_type',
            field=models.CharField(blank=True, default='application/octet-stream', max_length=120),
        ),
        migrations.AddField(
            model_name='techniciandocument',
            name='file_size',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='techniciandocument',
            name='document_type',
            field=models.CharField(
                choices=[
                    ('piece_identite', 'CNI ou pièce d’identité'),
                    ('certificat', 'Certificat professionnel'),
                    ('experience', 'Justificatif d’expérience'),
                    ('assurance', 'Assurance'),
                    ('autre', 'Autre document'),
                ],
                default='autre',
                max_length=40,
            ),
        ),
        migrations.AddIndex(
            model_name='techniciandocument',
            index=models.Index(fields=['technician', 'validation_status'], name='techdoc_tech_status_idx'),
        ),
        migrations.AddIndex(
            model_name='techniciandocument',
            index=models.Index(fields=['document_type'], name='techdoc_type_idx'),
        ),
        migrations.RunPython(migrate_existing_files_to_db, migrations.RunPython.noop),
    ]
