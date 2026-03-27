from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """
    Handler d'exception unifié.

    Toutes les erreurs retournent le format :
    {
        "error": true,
        "message": "Description courte",
        "details": { ... }   # champs de validation ou info supplémentaire
    }
    """
    response = exception_handler(exc, context)

    if response is None:
        return None

    error_data = response.data

    # Cas 1 : erreurs de validation DRF (dict de champs)
    if isinstance(error_data, dict):
        # Si la réponse a déjà notre format, ne pas re-wrapper
        if 'error' in error_data and 'message' in error_data:
            return response

        # Extraire un message lisible depuis les erreurs de champs
        non_field = error_data.get('non_field_errors') or error_data.get('detail')
        if non_field:
            message = non_field[0] if isinstance(non_field, list) else str(non_field)
            details = {k: v for k, v in error_data.items() if k not in ('non_field_errors', 'detail')}
        else:
            first_key = next(iter(error_data), None)
            first_val = error_data.get(first_key, '')
            if isinstance(first_val, list):
                message = f"{first_key}: {first_val[0]}"
            else:
                message = str(first_val)
            details = error_data

        response.data = {
            'error': True,
            'message': message,
            'details': details if details != error_data else {},
        }

    # Cas 2 : liste d'erreurs
    elif isinstance(error_data, list):
        response.data = {
            'error': True,
            'message': str(error_data[0]) if error_data else 'Erreur inconnue',
            'details': {},
        }

    return response
