# Déploiement Docker / Render

## Variables minimales à définir
- `SECRET_KEY`
- `DATABASE_URL` (prendre l'Internal Database URL sur Render)
- `ALLOWED_HOSTS`
- `CORS_ALLOWED_ORIGINS`
- `CSRF_TRUSTED_ORIGINS`
- `DJANGO_SETTINGS_MODULE=config.settings.prod`

## Lancement Docker local
```bash
docker build -t willy-backend .
docker run --env-file .env -p 10000:10000 willy-backend
```

## Points importants
- Le backend écoute sur `0.0.0.0:$PORT`.
- Les migrations et `collectstatic` sont exécutées au démarrage.
- Si `REDIS_URL` n'est pas défini, les Channels basculent en mémoire pour éviter de bloquer le démarrage.
- Pour Render, utiliser l'URL interne PostgreSQL quand le backend et la base sont dans la même région.


## Correctif compatibilité Render
- `config/settings/render.py` est fourni comme alias vers `config.settings.prod` pour éviter qu'une ancienne variable `DJANGO_SETTINGS_MODULE=config.settings.render` casse le déploiement.
- Si ton service Render possède encore cette ancienne variable, le projet démarrera quand même.
