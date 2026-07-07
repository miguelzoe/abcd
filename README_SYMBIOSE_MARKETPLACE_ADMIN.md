# Symbiose Cartronic — Backend + Marketplace + Administration

Ce backend Django/DRF sert de point central pour les applications Cartronic :

- marketplace_cartronic mobile ;
- frontend d'administration EFGH ;
- intervention_cartronic via la même base et les mêmes utilisateurs, sans modification de son code dans cette archive.

## Intégrations ajoutées

### API Marketplace mobile/admin

Routes disponibles sous `/api/` :

- `GET/POST /api/marketplace-vehicles/`
- `GET/PATCH/DELETE /api/marketplace-vehicles/{id}/`
- `GET /api/marketplace-vehicles/featured/`
- `GET /api/marketplace-vehicles/{id}/availability/`
- `GET /api/marketplace-vehicles/{id}/reviews/`
- `GET/POST /api/marketplace-orders/`
- `GET/PATCH/DELETE /api/marketplace-orders/{id}/`
- `POST /api/marketplace-orders/{id}/pay/`
- `POST /api/marketplace-orders/{id}/cancel/`
- `POST /api/marketplace-orders/{id}/update_status/`
- `GET/POST /api/pieces/`
- `GET/PATCH/DELETE /api/pieces/{id}/`
- `GET/POST /api/marketplace-article-types/`

### API administration EFGH

- `GET /api/admin/marketplace/summary/`

Cette route alimente le tableau de bord Marketplace dans EFGH avec : commandes, revenus, véhicules, pièces, types d'articles, commandes récentes et répartition par statut/type.

## Base de données partagée

La logique conserve une base commune. Les utilisateurs restent portés par le modèle `User` existant et ses profils (`Client`, `Vendor`, `Technician`, `Administrator`). Un utilisateur peut donc :

- utiliser uniquement marketplace_cartronic ;
- utiliser uniquement intervention_cartronic ;
- utiliser les deux applications avec le même compte.

## Déploiement local

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# ou venv\\Scripts\\activate sous Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

## Vérification réalisée ici

```bash
python -m compileall -q apps config manage.py
```

La compilation Python passe. Le `manage.py check` n'a pas pu être exécuté dans le sandbox parce que Django n'est pas installé dans l'environnement global du sandbox.
