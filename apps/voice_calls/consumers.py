from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from apps.voice_calls.models import VoiceCallSession, VoiceCallSignal
from apps.voice_calls.services import call_group, user_group


@database_sync_to_async
def session_is_allowed(session_id: str, user_id: int):
    try:
        session = VoiceCallSession.objects.get(id=session_id)
    except VoiceCallSession.DoesNotExist:
        return False
    return user_id in {session.caller_id, session.callee_id}


@database_sync_to_async
def persist_signal(session_id: str, user, signal_type: str, payload: dict):
    session = VoiceCallSession.objects.get(id=session_id)
    return VoiceCallSignal.objects.create(
        session=session,
        sender=user,
        signal_type=signal_type,
        payload=payload or {},
    ).id


class VoicePresenceConsumer(AsyncJsonWebsocketConsumer):
    """Canal personnel: alerte d'appel entrant pendant que l'app est ouverte."""

    async def connect(self):
        user = self.scope.get('user')
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.group_name = user_group(user.id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({'event': 'presence_ready', 'server_time': timezone.now().isoformat()})

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get('event') == 'ping':
            await self.send_json({'event': 'pong', 'server_time': timezone.now().isoformat()})

    async def voice_event(self, event):
        await self.send_json({'event': event.get('event'), 'payload': event.get('payload')})


class VoiceCallConsumer(AsyncJsonWebsocketConsumer):
    """Salon de signalisation WebRTC pour une session d'appel."""

    async def connect(self):
        user = self.scope.get('user')
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        allowed = await session_is_allowed(self.session_id, user.id)
        if not allowed:
            await self.close(code=4403)
            return
        self.group_name = call_group(self.session_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({'event': 'call_socket_ready', 'session_id': self.session_id})

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        user = self.scope['user']
        signal_type = str(content.get('signal_type') or content.get('event') or '').strip()
        payload = content.get('payload') or {}
        allowed_types = {'offer', 'answer', 'ice-candidate', 'mute-state', 'failed', 'ended'}
        if signal_type not in allowed_types:
            await self.send_json({'event': 'error', 'message': 'Signal invalide.'})
            return
        signal_id = await persist_signal(self.session_id, user, signal_type, payload)
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'voice.signal',
                'sender_id': user.id,
                'signal_id': signal_id,
                'signal_type': signal_type,
                'payload': payload,
                'created_at': timezone.now().isoformat(),
            },
        )

    async def voice_signal(self, event):
        await self.send_json({'event': 'signal', **event})

    async def voice_event(self, event):
        await self.send_json({'event': event.get('event'), 'payload': event.get('payload')})
