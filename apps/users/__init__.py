default_app_config = 'apps.users.apps.UsersConfig'

# Importer les signaux pour qu'ils soient enregistrés
def ready():
    import apps.users.signals