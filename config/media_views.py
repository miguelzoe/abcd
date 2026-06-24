import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.utils._os import safe_join
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_GET


@require_GET
@xframe_options_exempt
def serve_media_file(request, path):
    """Serve uploaded media files, including technician documents, in production.

    Render deployments run with DEBUG=False, so django.conf.urls.static.static()
    does not expose /media/. This view intentionally serves MEDIA_ROOT files and
    sets inline headers so PDFs/images can be previewed by the admin Angular app.
    """
    try:
        full_path = Path(safe_join(str(settings.MEDIA_ROOT), path))
    except ValueError as exc:
        raise Http404('Fichier introuvable.') from exc

    if not full_path.exists() or not full_path.is_file():
        raise Http404('Fichier introuvable.')

    content_type, _ = mimetypes.guess_type(str(full_path))
    content_type = content_type or 'application/octet-stream'

    response = FileResponse(open(full_path, 'rb'), content_type=content_type)
    response['Content-Disposition'] = f'inline; filename="{full_path.name}"'
    response['Cache-Control'] = 'private, max-age=300'
    response['X-Content-Type-Options'] = 'nosniff'
    # Do not block the admin frontend iframe when it previews PDFs from another origin.
    response.headers.pop('X-Frame-Options', None)
    return response
