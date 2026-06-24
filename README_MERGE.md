Backend fusionné basé sur `willy_project` + `admin_panel` et workflow de validation issus de `willy_project-victoire`.

Étapes recommandées :
1. Copier `.env.example` vers `.env`
2. Installer `requirements.txt`
3. Lancer `python manage.py migrate`
4. Lancer `python manage.py runserver`

Endpoints ajoutés :
- `/api/admin/*`
- `/api/auth/forgot-password/`
- `/api/auth/reset-password/`
