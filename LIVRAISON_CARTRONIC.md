# Livraison Cartronic — Backend + Intervention + Marketplace + Admin

## 1. Ce qui a été corrigé / ajouté

### Backend Django
- Ajout d’un flux **mot de passe oublié Intervention Cartronic** séparé du flux administrateur existant.
- Endpoints ajoutés :
  - `POST /api/intervention/auth/forgot-password/`
  - `POST /api/intervention/auth/reset-password/`
- Ces endpoints ne ciblent que les comptes `client` et `technician`.
- Le flux admin existant reste séparé :
  - `POST /api/auth/forgot-password/`
  - `POST /api/auth/reset-password/`
- Correction des validations d’inscription client/technicien : téléphone normalisé, email en minuscule, contrôle des doublons email/téléphone/username, et gestion plus robuste des spécialités technicien.
- Ajout d’une vraie séparation logique des comptes marketplace :
  - `marketplace_customer` : client marketplace simple.
  - `vendor` : vendeur marketplace accrédité.
  - `auto_shop` : boutique automobile / location accréditée.
- Ajout du modèle `MarketplacePartnerApplication` pour les demandes d’accréditation vendeur/boutique.
- Ajout des endpoints marketplace :
  - `POST /api/marketplace-auth/register/`
  - `POST /api/marketplace-auth/login/`
  - `GET /api/marketplace-auth/me/`
  - `POST /api/marketplace-auth/forgot-password/`
  - `POST /api/marketplace-auth/reset-password/`
  - `/api/marketplace-partner-applications/`
- Ajout des endpoints admin pour valider/refuser les partenaires :
  - `GET /api/admin/marketplace/partners/`
  - `POST /api/admin/marketplace/partners/<id>/approve/`
  - `POST /api/admin/marketplace/partners/<id>/reject/`
- Les commandes marketplace peuvent maintenant être liées à un vrai compte marketplace via `marketplace_user`, sans dépendre des profils client intervention.
- Dockerfile backend réécrit pour Django + DRF + Daphne + PostgreSQL/PostGIS/GDAL.

### Application mobile intervention-cartronic
- Ajout de la logique frontend sur l’écran existant/nouveau de mot de passe oublié.
- Raccordement aux endpoints intervention : `/api/intervention/auth/...`.
- Correction de l’inscription technicien/client : envoi FormData sans forcer manuellement le header `Content-Type`, ce qui évite les blocages multipart sur mobile.
- Les spécialités technicien sont envoyées proprement sous forme compatible avec le backend.

### Application mobile marketplace_cartronic
- L’inscription marketplace crée maintenant un compte `marketplace_customer`, séparé de l’application intervention.
- Login/me/reset password raccordés aux endpoints `marketplace-auth`.
- La réinitialisation de mot de passe utilise un vrai token backend, pas un OTP mock `123456`.
- Le compte vendeur/boutique passe désormais par une demande d’accréditation validable par l’administration.

### Frontend admin EFGH
- Ajout d’une page **Partenaires Market**.
- Ajout du service Angular pour charger, valider et refuser les demandes d’accréditation marketplace.
- Ajout des nouveaux indicateurs marketplace côté dashboard admin : demandes partenaires, partenaires approuvés, vendeurs, boutiques automobiles.

## 2. Variables d’environnement utiles

Dans le backend :

```env
INTERVENTION_FRONTEND_URL=cartronic://forgot-password
INTERVENTION_PASSWORD_RESET_EXPOSE_TOKEN=True
MARKETPLACE_FRONTEND_URL=marketplacecartronic://auth/forgot-password
MARKETPLACE_PASSWORD_RESET_EXPOSE_TOKEN=True
```

En production réelle, vous pourrez passer `*_PASSWORD_RESET_EXPOSE_TOKEN=False` lorsque l’envoi email SMTP est bien configuré.

## 3. Migrations à exécuter

Après déploiement du backend :

```bash
python manage.py makemigrations --check
python manage.py migrate
python manage.py collectstatic --noinput
```

Les migrations manuelles ajoutées sont :

- `apps/users/migrations/0013_marketplace_user_roles_vendor_accreditation.py`
- `apps/marketplace/migrations/0005_marketplace_users_partner_applications.py`

## 4. Docker backend

Construction :

```bash
docker build -t cartronic-backend:latest .
```

Lancement exemple :

```bash
docker run --env-file .env -p 8000:8000 cartronic-backend:latest
```

## 5. Vérifications effectuées

- Compilation Python complète du backend avec `compileall` : OK.
- Vérification syntaxique des fichiers backend modifiés : OK.
- Les builds Expo/Angular complets n’ont pas été lancés ici car les dépendances `node_modules` ne sont pas installées dans l’environnement de travail.
