# API backend ajoutée pour marketplace_cartronic

Cette version ajoute des endpoints dédiés à la marketplace mobile sans modifier les APIs existantes d'intervention.

## Nouveaux modèles

- `MarketplaceVehicle` : véhicules de vente/location affichés dans `marketplace_cartronic`.
- `MarketplaceOrder` : commandes mobiles pour pièces, achat véhicule et location véhicule.

Ces modèles sont séparés de `apps.vehicles.Vehicle` afin de ne pas impacter le module intervention.

## Nouveaux endpoints

- `GET /api/marketplace-vehicles/`
- `GET /api/marketplace-vehicles/{id}/`
- `GET /api/marketplace-vehicles/featured/?limit=5`
- `GET /api/marketplace-vehicles/{id}/availability/?start_date=...&end_date=...`
- `GET /api/marketplace-orders/`
- `POST /api/marketplace-orders/`
- `POST /api/marketplace-orders/{id}/cancel/`
- `POST /api/marketplace-orders/{id}/pay/`
- `POST /api/marketplace-orders/{id}/update_status/`

Des routes de compatibilité existent aussi sous `/api/marketplace/vehicles/` et `/api/marketplace/orders/`.

## Migration

Appliquer les migrations :

```bash
python manage.py migrate
```

La migration `0004_marketplace_mobile_api.py` crée les nouvelles tables et ajoute quelques véhicules de démonstration actifs pour que l'application mobile affiche immédiatement des données.
