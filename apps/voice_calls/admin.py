from django.contrib import admin
from apps.voice_calls.models import VoiceCallSession, VoiceCallSignal


@admin.register(VoiceCallSession)
class VoiceCallSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'reservation', 'caller', 'callee', 'status', 'duration_seconds', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('id', 'caller__username', 'callee__username', 'caller__telephone', 'callee__telephone')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(VoiceCallSignal)
class VoiceCallSignalAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'sender', 'signal_type', 'created_at')
    list_filter = ('signal_type', 'created_at')
    search_fields = ('session__id', 'sender__username')
