from django.contrib import admin
from .models import ChatSession, ChatMessage, GuestChatLog


class ChatMessageInline(admin.TabularInline):
    model          = ChatMessage
    extra          = 0
    readonly_fields = ('role', 'content', 'created_at')
    can_delete     = False
    max_num        = 0


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display    = ('user', 'mode', 'session_key', 'is_active', 'created_at', 'updated_at')
    list_filter     = ('mode', 'is_active')
    search_fields   = ('user__email', 'session_key')
    readonly_fields = ('session_key', 'created_at', 'updated_at')
    inlines         = [ChatMessageInline]
    ordering        = ['-updated_at']


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display  = ('session', 'role', 'short_content', 'created_at')
    list_filter   = ('role',)
    search_fields = ('content', 'session__user__email')
    readonly_fields = ('created_at',)

    @admin.display(description='Content')
    def short_content(self, obj):
        return (obj.content[:80] + '…') if len(obj.content) > 80 else obj.content


@admin.register(GuestChatLog)
class GuestChatLogAdmin(admin.ModelAdmin):
    list_display  = ('session_key', 'ip_address', 'short_message', 'created_at')
    readonly_fields = ('created_at',)
    search_fields = ('ip_address',)

    @admin.display(description='User Message')
    def short_message(self, obj):
        return (obj.user_message[:60] + '…') if len(obj.user_message) > 60 else obj.user_message