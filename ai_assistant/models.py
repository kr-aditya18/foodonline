from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ChatSession(models.Model):
    """Stores a single chat session per user."""
    MODE_CHOICES = [
        ('customer', 'Customer Assistant'),
        ('vendor',   'Vendor Assistant'),
    ]

    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions')
    mode        = models.CharField(max_length=20, choices=MODE_CHOICES, default='customer')
    session_key = models.CharField(max_length=64, unique=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    is_active   = models.BooleanField(default=True)

    class Meta:
        ordering      = ['-updated_at']
        verbose_name  = 'Chat Session'
        verbose_name_plural = 'Chat Sessions'

    def __str__(self):
        return f"{self.user.email} - {self.mode} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class ChatMessage(models.Model):
    """Stores individual messages within a chat session."""
    ROLE_CHOICES = [
        ('user',      'User'),
        ('assistant', 'Assistant'),
        ('system',    'System'),
    ]

    session    = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role       = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    metadata   = models.JSONField(null=True, blank=True)   # for structured AI responses later

    class Meta:
        ordering      = ['created_at']
        verbose_name  = 'Chat Message'
        verbose_name_plural = 'Chat Messages'

    def __str__(self):
        preview = self.content[:60]
        return f"[{self.role}] {preview}..."

    def to_dict(self):
        """Return dict suitable for OpenRouter message payload."""
        return {'role': self.role, 'content': self.content}


class GuestChatLog(models.Model):
    """Lightweight log for unauthenticated guest chat (no sensitive data stored)."""
    session_key     = models.CharField(max_length=64)
    user_message    = models.TextField()
    assistant_reply = models.TextField()
    created_at      = models.DateTimeField(auto_now_add=True)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering      = ['-created_at']
        verbose_name  = 'Guest Chat Log'
        verbose_name_plural = 'Guest Chat Logs'

    def __str__(self):
        return f"Guest [{self.ip_address}] - {self.created_at.strftime('%Y-%m-%d %H:%M')}"