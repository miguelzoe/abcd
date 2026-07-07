# Cartronic — Documents techniciens stockés en base de données

Cette version supprime la dépendance à Render Disk pour les documents justificatifs des techniciens.

## Principe

- Les nouveaux documents envoyés par un technicien sont lus depuis le formulaire multipart.
- Leur contenu binaire est stocké dans PostgreSQL via le champ `TechnicianDocument.file_data`.
- Les métadonnées sont aussi conservées : nom original, type MIME, taille, type de document, statut de validation.
- L'ancien champ `file` est conservé uniquement pour compatibilité avec les documents déjà existants.

## Endpoint de visualisation admin

```http
GET /api/admin/users/<user_id>/documents/<document_id>/view/
```

Cet endpoint est protégé par la permission administrateur et renvoie le document avec `Content-Disposition: inline`, afin que l'admin puisse visualiser PDF et images directement dans l'interface.

## Migration

Lancer :

```bash
python manage.py migrate
```

La migration `0010_store_technician_documents_in_db.py` tente de copier les anciens fichiers `/media` vers la base si les fichiers existent encore physiquement. Si Render les a déjà supprimés, seuls les nouveaux documents uploadés seront disponibles en base.

## Recommandation

Limiter les documents à 5 Mo et aux formats PDF/JPG/PNG/WEBP, ce qui est déjà appliqué dans le serializer d'inscription technicien.
