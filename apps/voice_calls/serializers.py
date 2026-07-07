from rest_framework import serializers
from apps.voice_calls.models import VoiceCallSession, VoiceCallSignal


class MinimalUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    telephone = serializers.CharField(allow_blank=True)
    user_type = serializers.CharField()
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        name = obj.get_full_name() if hasattr(obj, 'get_full_name') else ''
        return name or getattr(obj, 'username', '')


class VoiceCallSessionSerializer(serializers.ModelSerializer):
    caller = MinimalUserSerializer(read_only=True)
    callee = MinimalUserSerializer(read_only=True)
    reservation_id = serializers.IntegerField(source='reservation.id', read_only=True)
    is_caller = serializers.SerializerMethodField()
    is_callee = serializers.SerializerMethodField()

    class Meta:
        model = VoiceCallSession
        fields = [
            'id', 'reservation_id', 'caller', 'callee', 'status',
            'started_at', 'answered_at', 'ended_at', 'duration_seconds',
            'end_reason', 'metadata', 'is_caller', 'is_callee', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_is_caller(self, obj):
        request = self.context.get('request')
        return bool(request and request.user and obj.caller_id == request.user.id)

    def get_is_callee(self, obj):
        request = self.context.get('request')
        return bool(request and request.user and obj.callee_id == request.user.id)


class VoiceCallSignalSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)

    class Meta:
        model = VoiceCallSignal
        fields = ['id', 'session', 'sender', 'sender_id', 'signal_type', 'payload', 'created_at']
        read_only_fields = ['id', 'sender', 'sender_id', 'created_at']
