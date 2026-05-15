import uuid
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# ROLE DETECTION
# ──────────────────────────────────────────────────────────────

def get_user_role(user):
    """
    Returns 'vendor', 'customer', or 'guest'.
    FoodOnline stores role as an integer on the User model:
        1 = Customer
        2 = Vendor
    ⚠️  If your project uses different values, update below.
    Check your accounts/models.py User model constants.
    """
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


# ──────────────────────────────────────────────────────────────
# SYSTEM PROMPTS  (role-based)
# ──────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────
# OPENROUTER API CLIENT
# ──────────────────────────────────────────────────────────────

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Free models — tried in order if one is rate-limited
FREE_MODELS = [
    "meta-llama/llama-3.1-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "google/gemma-2-9b-it:free",
]


def call_openrouter(messages, role='guest', model=None):
    """
    Send messages to OpenRouter and return AI reply.

    Args:
        messages : list of {'role': ..., 'content': ...}
        role     : 'vendor' | 'customer' | 'guest'
        model    : override model string (optional)

    Returns:
        {'success': bool, 'reply': str, 'error': str|None}
    """
    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')

    if not api_key:
        logger.warning("OPENROUTER_API_KEY not set.")
        return {
            'success': False,
            'reply': "⚙️ AI assistant is not configured yet. "
                     "Please set the OPENROUTER_API_KEY environment variable.",
            'error': 'API key not configured',
        }

    system_prompt = get_system_prompt(role)
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": getattr(settings, 'SITE_URL', 'https://foodonline.onrender.com'),
        "X-Title": "FoodOnline AI Assistant",
    }

    models_to_try = ([model] if model else []) + FREE_MODELS

    for attempt_model in models_to_try:
        payload = {
            "model": attempt_model,
            "messages": full_messages,
            "max_tokens": 512,
            "temperature": 0.7,
        }
        try:
            resp = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=30)

            if resp.status_code == 200:
                reply = resp.json()['choices'][0]['message']['content'].strip()
                logger.info(f"OpenRouter OK — model: {attempt_model}")
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
            logger.error(f"Request error: {e}")
            continue

    return {
        'success': False,
        'reply': "🙏 I'm having trouble connecting right now. Please try again in a moment!",
        'error': 'All models failed',
    }


# ──────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────

def build_message_history(session, max_messages=10):
    """Return last N user/assistant messages as list of dicts."""
    qs = session.messages.filter(
        role__in=['user', 'assistant']
    ).order_by('-created_at')[:max_messages]
    return [m.to_dict() for m in reversed(qs)]


def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')