# Willy Backend

Backend Django/PostGIS prêt pour Docker et Render.

## Ce qui a été corrigé
- configuration GeoDjango rendue portable (plus de chemins Windows en dur)
- support de `DATABASE_URL` pour Render
- fallback propre sans Redis pour éviter les blocages de démarrage
- serveur ASGI de production avec Gunicorn + Uvicorn
- support des fichiers statiques avec WhiteNoise
- endpoint de santé `/health/`
- `Dockerfile`, `entrypoint.sh`, `.dockerignore` et `.env.example` propres

## Déploiement rapide
1. Renseigner les variables d'environnement (voir `.env.example`).
2. Utiliser l'**Internal Database URL** de Render dans `DATABASE_URL`.
3. Construire et lancer :
   ```bash
   docker build -t willy-backend .
   docker run --env-file .env -p 10000:10000 willy-backend
   ```

## Health check
- `GET /health/`
