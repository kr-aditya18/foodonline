import uuid
import time
import requests
import logging
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import json
import re

logger = logging.getLogger(__name__)


# ── ROLE DETECTION ──────────────────────────────────────────────────────────

def get_user_role(user):
    if not user or not user.is_authenticated:
        return 'guest'
    role = getattr(user, 'role', None)
    if role == 1:
        return 'vendor'
    elif role == 2:
        return 'customer'
    return 'guest'


def generate_session_key():
    return uuid.uuid4().hex


# ── SYSTEM PROMPTS ───────────────────────────────────────────────────────────

VENDOR_SYSTEM_PROMPT = """You are an AI assistant for FoodOnline, a multi-vendor restaurant marketplace.
You are helping a VENDOR (restaurant owner) manage their menu and business.

Your capabilities:
- Generate food item title, description, category, price, and tags from a natural description
- Compare pricing with market trends
- Suggest menu improvements
- Answer vendor-related platform questions

When generating food item details always respond in this EXACT format:
**Title:** <food item name>
**Description:** <appetizing 1-2 sentence description>
**Category:** <e.g. Starters, Main Course, Desserts, Beverages, Snacks>
**Suggested Price:** <price in INR, e.g. ₹199>
**Tags:** <comma-separated keywords>

Be concise, professional. Lean toward Indian food culture where relevant."""


CUSTOMER_SYSTEM_PROMPT = """You are an AI food assistant for FoodOnline, a multi-vendor restaurant marketplace.
You are helping a CUSTOMER discover food and restaurants.

Your capabilities:
- Recommend food based on mood, craving, or preferences
- Help discover nearby restaurants
- Answer food and cuisine questions
- Help with order support questions

Be warm, friendly, and enthusiastic about food. Use emojis occasionally.
When recommending food, explain WHY it matches the customer's mood or craving.
For ordering guidance, direct them to use the search/browse features on FoodOnline."""


GUEST_SYSTEM_PROMPT = """You are an AI food assistant for FoodOnline, a multi-vendor restaurant marketplace.
A guest (not logged in) is chatting with you.

You can:
- Answer general questions about FoodOnline
- Explain how the platform works
- Encourage registration/login for full features
- Answer basic food and cuisine questions

Always mention that logging in enables personalized recommendations and ordering.
Be welcoming and helpful."""


def get_system_prompt(role):
    return {
        'vendor':   VENDOR_SYSTEM_PROMPT,
        'customer': CUSTOMER_SYSTEM_PROMPT,
        'guest':    GUEST_SYSTEM_PROMPT,
    }.get(role, GUEST_SYSTEM_PROMPT)


# ══════════════════════════════════════════════════════════════════
# PHASE 10 — RATE LIMITING
# ══════════════════════════════════════════════════════════════════

# Limits — tweak these any time in settings.py via AI_RATE_LIMITS
DEFAULT_RATE_LIMITS = {
    'user_per_minute': 10,    # authenticated users: max 10 msgs/min
    'user_per_day':    200,   # authenticated users: max 200 msgs/day
    'guest_per_day':   20,    # guests (by IP):      max 20 msgs/day
}


def _get_limits():
    return getattr(settings, 'AI_RATE_LIMITS', DEFAULT_RATE_LIMITS)


def check_rate_limit(user=None, ip=None):
    """
    Check if the request is within rate limits.
    Returns (allowed: bool, reason: str)

    Uses RateLimitBucket model — no Redis needed.
    Expired buckets are reset automatically on next hit.
    """
    from .models import RateLimitBucket

    limits  = _get_limits()
    now     = timezone.now()

    if user and user.is_authenticated:
        identifier = f"user_{user.id}"

        # ── Per-minute check ────────────────────────────────────
        minute_limit = limits.get('user_per_minute', 10)
        bucket_min, _ = RateLimitBucket.objects.get_or_create(
            identifier=identifier,
            window='minute',
            defaults={'count': 0, 'reset_at': now + timedelta(minutes=1)},
        )
        if now >= bucket_min.reset_at:
            # Window expired — reset
            bucket_min.count    = 0
            bucket_min.reset_at = now + timedelta(minutes=1)

        bucket_min.count += 1
        bucket_min.save(update_fields=['count', 'reset_at'])

        if bucket_min.count > minute_limit:
            secs_left = max(0, int((bucket_min.reset_at - now).total_seconds()))
            return False, f"⏳ You're sending messages too quickly. Please wait {secs_left}s before trying again."

        # ── Per-day check ───────────────────────────────────────
        day_limit = limits.get('user_per_day', 200)
        bucket_day, _ = RateLimitBucket.objects.get_or_create(
            identifier=identifier,
            window='day',
            defaults={'count': 0, 'reset_at': now + timedelta(days=1)},
        )
        if now >= bucket_day.reset_at:
            bucket_day.count    = 0
            bucket_day.reset_at = now + timedelta(days=1)

        bucket_day.count += 1
        bucket_day.save(update_fields=['count', 'reset_at'])

        if bucket_day.count > day_limit:
            return False, "📅 You've reached your daily AI message limit. It resets at midnight — come back tomorrow!"

        return True, ''

    else:
        # ── Guest: per-day by IP ────────────────────────────────
        if not ip:
            return True, ''   # no IP = can't rate-limit, let through

        guest_limit = limits.get('guest_per_day', 20)
        identifier  = f"ip_{ip}"
        bucket, _ = RateLimitBucket.objects.get_or_create(
            identifier=identifier,
            window='day',
            defaults={'count': 0, 'reset_at': now + timedelta(days=1)},
        )
        if now >= bucket.reset_at:
            bucket.count    = 0
            bucket.reset_at = now + timedelta(days=1)

        bucket.count += 1
        bucket.save(update_fields=['count', 'reset_at'])

        if bucket.count > guest_limit:
            return False, "🔐 You've used all your free guest messages today. Log in for more!"

        return True, ''


# ══════════════════════════════════════════════════════════════════
# PHASE 10 — INTERACTION LOGGER
# ══════════════════════════════════════════════════════════════════

def log_interaction(
    user=None, role='guest', ip=None, session_key='',
    feature='chat', user_message='', ai_reply='',
    model_used='', success=True, error_message='',
    response_time_ms=0,
):
    """
    Write one row to AIInteractionLog.
    Non-blocking — errors are swallowed so a log failure never breaks the chat.
    """
    try:
        from .models import AIInteractionLog
        AIInteractionLog.objects.create(
            user             = user if (user and user.is_authenticated) else None,
            role             = role,
            ip_address       = ip,
            session_key      = session_key or '',
            feature          = feature,
            user_message     = (user_message or '')[:2000],   # cap length
            ai_reply         = (ai_reply or '')[:2000],
            model_used       = model_used or '',
            success          = success,
            error_message    = (error_message or '')[:500],
            response_time_ms = response_time_ms,
        )
    except Exception as e:
        logger.warning(f"[AILog] Failed to write interaction log: {e}")


# ── OPENROUTER CLIENT ────────────────────────────────────────────────────────

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

FREE_MODELS = [
    "openrouter/auto",
    "meta-llama/llama-3.1-8b-instruct:free",
    "microsoft/phi-3-mini-128k-instruct:free",
    "google/gemma-2-9b-it:free",
    "mistralai/mistral-7b-instruct:free",
]


def call_openrouter(
    messages, role='guest', model=None,
    # Phase 10 logging context — pass these from views
    user=None, ip=None, session_key='', feature='chat', user_message='',
):
    """
    Send messages to OpenRouter and return AI reply.
    Injects a role-based system prompt automatically.
    Logs every call to AIInteractionLog (Phase 10).

    Returns: {'success': bool, 'reply': str, 'error': str|None}
    """
    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
    if not api_key:
        logger.warning("OPENROUTER_API_KEY not set.")
        _reply = "⚙️ AI assistant is not configured yet. Please set the OPENROUTER_API_KEY environment variable."
        log_interaction(
            user=user, role=role, ip=ip, session_key=session_key,
            feature=feature, user_message=user_message, ai_reply=_reply,
            success=False, error_message='API key not configured',
        )
        return {'success': False, 'reply': _reply, 'error': 'API key not configured'}

    system_prompt = get_system_prompt(role)
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  getattr(settings, 'SITE_URL', 'https://foodonline.onrender.com'),
        "X-Title":       "FoodOnline AI Assistant",
    }

    models_to_try = ([model] if model else []) + FREE_MODELS
    start_time    = time.time()

    for attempt_model in models_to_try:
        try:
            resp = requests.post(
                OPENROUTER_API_URL,
                headers=headers,
                json={
                    "model":       attempt_model,
                    "messages":    full_messages,
                    "max_tokens":  512,
                    "temperature": 0.7,
                },
                timeout=30,
            )

            if resp.status_code == 200:
                data = resp.json()
                if 'choices' not in data:
                    logger.warning(f"No 'choices' in response from {attempt_model}: {data}")
                    continue
                content = data['choices'][0]['message'].get('content') or ''
                reply   = content.strip()
                if not reply:
                    logger.warning(f"Empty content from {attempt_model}, trying next…")
                    continue

                actual_model  = data.get('model', attempt_model)
                elapsed_ms    = int((time.time() - start_time) * 1000)
                logger.info(f"OpenRouter OK — model: {actual_model} | {elapsed_ms}ms")

                log_interaction(
                    user=user, role=role, ip=ip, session_key=session_key,
                    feature=feature, user_message=user_message, ai_reply=reply,
                    model_used=actual_model, success=True,
                    response_time_ms=elapsed_ms,
                )
                return {'success': True, 'reply': reply, 'error': None}

            elif resp.status_code == 429:
                logger.warning(f"Rate limit on {attempt_model}, trying next…")
                continue
            else:
                logger.error(f"OpenRouter {resp.status_code}: {resp.text[:200]}")
                continue

        except requests.exceptions.Timeout:
            logger.error(f"Timeout on {attempt_model}")
            continue
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error on {attempt_model}: {e}")
            continue

    elapsed_ms = int((time.time() - start_time) * 1000)
    _reply     = "🙏 I'm having trouble connecting right now. Please try again in a moment!"
    logger.error(f"[AI] All models failed after {elapsed_ms}ms — role:{role} feature:{feature}")

    log_interaction(
        user=user, role=role, ip=ip, session_key=session_key,
        feature=feature, user_message=user_message, ai_reply=_reply,
        model_used='all_failed', success=False,
        error_message='All models failed',
        response_time_ms=elapsed_ms,
    )
    return {'success': False, 'reply': _reply, 'error': 'All models failed'}


# ── HELPERS ──────────────────────────────────────────────────────────────────

def build_message_history(session, max_messages=10):
    qs = session.messages.filter(
        role__in=['user', 'assistant']
    ).order_by('-created_at')[:max_messages]
    return [m.to_dict() for m in reversed(qs)]


def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')


# ── FOOD ITEM GENERATOR ──────────────────────────────────────────────────────

def generate_food_item_structured(user_prompt, vendor_categories=None):
    """
    Ask the AI to generate a structured food menu item from a natural-language prompt.
    Returns a dict: {title, description, category, price, tags} or raises ValueError.
    """
    category_hint = ""
    if vendor_categories:
        names = ", ".join(vendor_categories)
        category_hint = (
            f"The vendor already has these categories: {names}. "
            "Reuse an existing one if it fits, otherwise suggest a new one."
        )

    system_prompt = f"""You are a professional food menu consultant helping a restaurant vendor.
When given a food idea, respond ONLY with a single valid JSON object — no markdown fences, no extra text.
Required keys:
{{
  "title":       "Short appealing dish name (3-6 words max)",
  "description": "1-2 sentence mouth-watering description",
  "category":    "Best-fit category name (e.g. Starters, Main Course, Desserts, Beverages, Snacks)",
  "price":       <suggested numeric price in INR, integer or float>,
  "tags":        ["tag1", "tag2", "tag3"]
}}
{category_hint}
Prices should be realistic for an Indian online food delivery platform (₹50-₹800 range).
Tags should be short keywords like "spicy", "vegan", "grilled", "best-seller" etc.
Return ONLY the JSON object. No explanation, no markdown, no extra text."""

    full_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ]

    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  getattr(settings, 'SITE_URL', 'https://foodonline.onrender.com'),
        "X-Title":       "FoodOnline AI Assistant",
    }

    raw = None
    for model in [
        "openrouter/auto",
        "google/gemma-3n-e4b-it:free",
        "arcee-ai/trinity-large-preview:free",
        "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
    ]:
        try:
            resp = requests.post(
                OPENROUTER_API_URL,
                headers=headers,
                json={
                    "model":       model,
                    "messages":    full_messages,
                    "max_tokens":  800,
                    "temperature": 0.2,
                },
                timeout=30,
            )
            if resp.status_code == 200:
                raw = resp.json()['choices'][0]['message']['content'].strip()
                logger.info(f"Food gen OK — model: {model}")
                break
            else:
                logger.error(f"Food gen {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Food gen error on {model}: {e}")
            continue

    if not raw:
        raise ValueError("All models failed")

    raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"AI returned non-JSON: {raw[:200]}")

    required = {"title", "description", "category", "price", "tags"}
    missing  = required - data.keys()
    if missing:
        raise ValueError(f"AI response missing keys: {missing}")

    data["price"] = float(data["price"])
    if not isinstance(data["tags"], list):
        data["tags"] = [str(data["tags"])]

    return data


def get_vendor_categories(vendor):
    try:
        from menu.models import Category
        return list(
            Category.objects.filter(vendor=vendor).values_list("category_name", flat=True)
        )
    except Exception:
        return []