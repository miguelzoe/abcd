# Willy Backend

Backend Django/DRF préparé pour le déploiement Docker avec **une seule variable d'environnement de base de données : `DATABASE_URL`**.

## Variables principales
Copiez `.env.example` vers `.env`, puis adaptez les valeurs :

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/willy_db
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1
```

## Lancement local sans Docker
```bash
python -m venv .venv
source .venv/bin/activate  # sous Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

## Lancement avec Docker
```bash
docker build -t willy-backend .
docker run --env-file .env -p 8000:8000 willy-backend
```

## Lancement avec Docker Compose
```bash
cp .env.example .env
docker compose up --build
```

## Fichiers ajoutés pour le déploiement
- `Dockerfile`
- `entrypoint.sh`
- `.dockerignore`
- `docker-compose.yml`
- `config/__init__.py`
- `config/settings/__init__.py`

## Endpoint de santé
```
GET /api/health/
```

## Notes importantes
- Le backend lit désormais la base de données depuis `DATABASE_URL`.
- Les anciennes variables `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT` ne sont plus nécessaires.
- Le zip livré a été nettoyé des environnements virtuels et des secrets présents dans les anciens fichiers `.env`.


## Local Windows note (GeoDjango)

If you run this backend on Windows, GeoDjango needs native GDAL/GEOS libraries.
This project now tries to auto-detect them from common locations such as OSGeo4W,
QGIS, PostgreSQL GIS binaries, and Python virtual environments.

Recommended local setup:

1. Install OSGeo4W with GDAL selected.
2. Copy `.env.example` to `.env`.
3. Set only `DATABASE_URL` for the database.
4. If auto-detection still fails, fill `GDAL_LIBRARY_PATH`, `GEOS_LIBRARY_PATH`, and `OSGEO4W_ROOT` in `.env`.

If you use Python 3.14 locally, prefer Django 5.2.x for compatibility.


## Déploiement actuellement câblé
- Frontend Vercel: https://efgh-3h6w.vercel.app
- Backend Render: https://backend-plxk.onrender.com
- API de base: https://backend-plxk.onrender.com/api
