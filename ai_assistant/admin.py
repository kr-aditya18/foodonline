# ai_assistant/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import ChatSession, ChatMessage, GuestChatLog, AIInteractionLog, RateLimitBucket


# ── ChatSession ──────────────────────────────────────────────────────────────

class ChatMessageInline(admin.TabularInline):
    model           = ChatMessage
    extra           = 0
    readonly_fields = ('role', 'content', 'created_at')
    can_delete      = False
    max_num         = 20
    ordering        = ('created_at',)


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display    = ('user', 'mode', 'is_active', 'message_count', 'created_at', 'updated_at')
    list_filter     = ('mode', 'is_active', 'created_at')
    search_fields   = ('user__email', 'session_key')
    readonly_fields = ('session_key', 'created_at', 'updated_at')
    inlines         = [ChatMessageInline]
    ordering        = ('-updated_at',)

    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Messages'


# ── GuestChatLog ─────────────────────────────────────────────────────────────

@admin.register(GuestChatLog)
class GuestChatLogAdmin(admin.ModelAdmin):
    list_display    = ('ip_address', 'short_message', 'created_at')
    list_filter     = ('created_at',)
    search_fields   = ('ip_address', 'user_message')
    readonly_fields = ('session_key', 'user_message', 'assistant_reply', 'ip_address', 'created_at')
    ordering        = ('-created_at',)

    def short_message(self, obj):
        msg = obj.user_message or ''
        return msg[:60] + ('...' if len(msg) > 60 else '')
    short_message.short_description = 'Message'


# ── AIInteractionLog ─────────────────────────────────────────────────────────

@admin.register(AIInteractionLog)
class AIInteractionLogAdmin(admin.ModelAdmin):
    list_display    = (
        'created_at', 'status_badge', 'role', 'feature',
        'user', 'ip_address', 'short_message',
        'short_reply', 'model_used', 'response_time_badge',
    )
    list_filter     = ('success', 'role', 'feature', 'created_at')
    search_fields   = ('user__email', 'ip_address', 'user_message', 'model_used', 'error_message')
    readonly_fields = (
        'user', 'role', 'ip_address', 'session_key', 'feature',
        'user_message', 'ai_reply', 'model_used',
        'success', 'error_message', 'response_time_ms', 'created_at',
    )
    ordering        = ('-created_at',)
    date_hierarchy  = 'created_at'

    def has_add_permission(self, request):              return False
    def has_change_permission(self, request, obj=None): return False

    def status_badge(self, obj):
        # Django 6 fix: mark_safe instead of format_html with no args
        if obj.success:
            return mark_safe('<span style="color:#27ae60;font-weight:700;">✅ OK</span>')
        return mark_safe('<span style="color:#e74c3c;font-weight:700;">❌ FAIL</span>')
    status_badge.short_description = 'Status'

    def response_time_badge(self, obj):
        ms = obj.response_time_ms or 0
        if ms < 1000:
            color = '#27ae60'   # green  — fast
        elif ms < 3000:
            color = '#f39c12'   # orange — medium
        else:
            color = '#e74c3c'   # red    — slow
        return format_html(
            '<span style="color:{};font-weight:600;">{}ms</span>',
            color, ms,
        )
    response_time_badge.short_description = 'Response Time'

    def short_message(self, obj):
        msg = obj.user_message or ''
        return msg[:50] + ('...' if len(msg) > 50 else '')
    short_message.short_description = 'Message'

    def short_reply(self, obj):
        reply = obj.ai_reply or ''
        return reply[:50] + ('...' if len(reply) > 50 else '')
    short_reply.short_description = 'AI Reply'


# ── RateLimitBucket ──────────────────────────────────────────────────────────

@admin.register(RateLimitBucket)
class RateLimitBucketAdmin(admin.ModelAdmin):
    list_display    = ('identifier', 'window', 'count', 'reset_at')
    list_filter     = ('window',)
    search_fields   = ('identifier',)
    readonly_fields = ('identifier', 'window', 'count', 'reset_at')
    ordering        = ('-count',)

    def has_add_permission(self, request): return False