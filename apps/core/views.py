from django.http import JsonResponse
from django.db import connection


def health_check(request):
    """Simple health endpoint for container orchestration and load balancers."""
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        db_ok = False

    status_code = 200 if db_ok else 503
    return JsonResponse(
        {
            'status': 'ok' if db_ok else 'degraded',
            'database': 'reachable' if db_ok else 'unreachable',
        },
        status=status_code,
    )
