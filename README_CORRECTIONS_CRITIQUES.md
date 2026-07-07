# Corrections critiques Cartronic

## 1. Documents techniciens

Le backend sert maintenant les fichiers `/media/...` même lorsque `DEBUG=False`, via `config.media_views.serve_media_file`.
Les PDF et images sont retournés avec `Content-Disposition: inline` pour permettre la prévisualisation côté admin.

Variables utiles en production Render :

```env
SERVE_MEDIA_IN_PRODUCTION=True
MEDIA_ROOT=/data/media
X_FRAME_OPTIONS=SAMEORIGIN
```

Pour une production fiable, ajouter un stockage persistant Render Disk monté sur `/data/media`, ou basculer vers S3/Cloudinary.
Sans stockage persistant, les fichiers uploadés peuvent disparaître après redéploiement.

## 2. Appels internes WebRTC

Le backend expose maintenant :

```http
GET /api/voice-calls/{id}/signals/?after_id=0
```

Cet endpoint permet au mobile de récupérer les signaux WebRTC par polling REST lorsque le WebSocket est instable.

## 3. Revenus et interventions par technicien

Nouvel endpoint admin :

```http
GET /api/admin/techniciens/performance/
```

Il retourne les revenus payés, les montants en attente, le nombre d'interventions, les missions terminées/en cours/annulées, la note moyenne et l'état des documents de chaque technicien.

## 4. Validation stricte des techniciens

Un technicien ne peut plus être approuvé si aucun document n'a été soumis ou si tous les documents ne sont pas validés.
