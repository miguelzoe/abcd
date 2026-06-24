from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

from apps.users.models import Notification
from apps.users.services import send_expo_push_to_user
from apps.voice_calls.serializers import VoiceCallSessionSerializer


def user_group(user_id: int) -> str:
    return f'voice_user_{user_id}'


def call_group(session_id: str) -> str:
    return f'voice_call_{session_id}'


def notify_voice_event(user, event_type: str, payload: dict):
    """Envoie un événement temps réel à un utilisateur connecté."""
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        user_group(user.id),
        {
            'type': 'voice.event',
            'event': event_type,
            'payload': payload,
        },
    )


def broadcast_call_event(session_id: str, event_type: str, payload: dict):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        call_group(str(session_id)),
        {
            'type': 'voice.event',
            'event': event_type,
            'payload': payload,
        },
    )


def session_payload(session, request=None) -> dict:
    return VoiceCallSessionSerializer(session, context={'request': request}).data


def create_call_notification(session, request=None):
    caller_name = session.caller.get_full_name() or session.caller.username
    title = 'Appel entrant'
    body = f'{caller_name} vous appelle dans Cartronic.'
    data = {
        'type': 'voice_call_incoming',
        'call_session_id': str(session.id),
        'reservation_id': session.reservation_id,
    }
    Notification.objects.create(user=session.callee, title=title, body=body, data=data)
    try:
        send_expo_push_to_user(session.callee, title=title, body=body, data=data)
    except Exception:
        pass

    notify_voice_event(
        session.callee,
        'incoming_call',
        {
            'session': session_payload(session, request=request),
            'server_time': timezone.now().isoformat(),
        },
    )
