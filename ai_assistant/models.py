from django.db import models
from cloudinary.models import CloudinaryField
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
    
# ══════════════════════════════════════════════════════════════════
# PHASE 10 — AI INTERACTION LOG + RATE LIMIT BUCKETS
# ══════════════════════════════════════════════════════════════════

class AIInteractionLog(models.Model):
    """
    Production log for every AI call made through the assistant.
    Stored in DB, visible in Django admin with filters.
    """
    ROLE_CHOICES = [
        ('vendor',   'Vendor'),
        ('customer', 'Customer'),
        ('guest',    'Guest'),
    ]
    FEATURE_CHOICES = [
        ('chat',        'General Chat'),
        ('food_gen',    'Food Item Generator'),
        ('price_cmp',   'Price Comparison'),
        ('recommend',   'Food Recommendations'),
        ('order_track', 'Order Tracking'),
        ('reorder',     'Reorder Suggestions'),
        ('nearby',      'Nearby Restaurants'),
        ('vendor_info',    'Vendor Info'),
        ('review_submit',  'Review Submission'),
        ('review_nudge',   'Review Nudge'),
        ('recommend_rated','Rated Recommendations'),
        ('onboarding',     'Onboarding Tour'),
    ]

    # Who
    user         = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ai_logs'
    )
    role         = models.CharField(max_length=20, choices=ROLE_CHOICES, default='guest')
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    session_key  = models.CharField(max_length=64, blank=True)

    # What
    feature      = models.CharField(max_length=30, choices=FEATURE_CHOICES, default='chat')
    user_message = models.TextField(blank=True)
    ai_reply     = models.TextField(blank=True)
    model_used   = models.CharField(max_length=120, blank=True)

    # How it went
    success          = models.BooleanField(default=True)
    error_message    = models.TextField(blank=True)
    response_time_ms = models.PositiveIntegerField(default=0)   # milliseconds

    # When
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering            = ['-created_at']
        verbose_name        = 'AI Interaction Log'
        verbose_name_plural = 'AI Interaction Logs'
        indexes = [
            models.Index(fields=['role', 'created_at']),
            models.Index(fields=['feature', 'created_at']),
            models.Index(fields=['success', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        who = self.user.email if self.user else f'Guest({self.ip_address})'
        ok  = '✅' if self.success else '❌'
        return f"{ok} [{self.feature}] {who} — {self.created_at.strftime('%d %b %H:%M')}"


class RateLimitBucket(models.Model):
    identifier = models.CharField(max_length=128)
    window     = models.CharField(max_length=10)
    count      = models.PositiveIntegerField(default=0)
    reset_at   = models.DateTimeField()

    class Meta:
        unique_together     = ('identifier', 'window')
        verbose_name        = 'Rate Limit Bucket'
        verbose_name_plural = 'Rate Limit Buckets'

    def __str__(self):
        return f"{self.identifier} [{self.window}] — {self.count} hits, resets {self.reset_at}"


# ══════════════════════════════════════════════════════════════════
# REVIEW SYSTEM
# ══════════════════════════════════════════════════════════════════

from django.core.validators import MinValueValidator, MaxValueValidator

class FoodReview(models.Model):
    customer   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='food_reviews')
    food_item  = models.ForeignKey('menu.FoodItem', on_delete=models.CASCADE, related_name='reviews')
    order      = models.ForeignKey('orders.Order', on_delete=models.CASCADE)
    order_item = models.ForeignKey('orders.OrderedFood', on_delete=models.CASCADE)
    rating     = models.DecimalField(
                     max_digits=2, decimal_places=1,
                     validators=[MinValueValidator(0.5), MaxValueValidator(5.0)]
                 )
    comment    = models.TextField(blank=True, max_length=500)
    image      = CloudinaryField('image', folder='review_images', blank=True, null=True)
    is_verified_purchase = models.BooleanField(default=True)
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('customer', 'order_item')
        ordering        = ['-created_at']
        verbose_name        = 'Food Review'
        verbose_name_plural = 'Food Reviews'

    def __str__(self):
        return f"{self.customer.email} → {self.food_item.food_title} ({self.rating}★)"


class ReviewReminder(models.Model):
    customer     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='review_reminders')
    order_item   = models.ForeignKey('orders.OrderedFood', on_delete=models.CASCADE)
    is_dismissed = models.BooleanField(default=False)
    reminded_at  = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('customer', 'order_item')
        verbose_name        = 'Review Reminder'
        verbose_name_plural = 'Review Reminders'

    def __str__(self):
        return f"Reminder: {self.customer.email} → {self.order_item.fooditem.food_title}"


# ══════════════════════════════════════════════════════════════════
# ONBOARDING TOUR
# ══════════════════════════════════════════════════════════════════

class OnboardingTour(models.Model):
    user           = models.OneToOneField(User, on_delete=models.CASCADE, related_name='onboarding')
    tour_completed = models.BooleanField(default=False)
    tour_step      = models.PositiveSmallIntegerField(default=0)
    completed_at   = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Onboarding Tour'
        verbose_name_plural = 'Onboarding Tours'

    def __str__(self):
        return f"{self.user.email} — step {self.tour_step} {'✅' if self.tour_completed else '⏳'}"