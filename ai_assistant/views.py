import json
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods
from .models import ChatSession, ChatMessage, GuestChatLog

from .utils_phase3 import build_price_comparison_data, format_comparison_for_ai
from .utils import (
    get_user_role,
    generate_session_key,
    call_openrouter,
    build_message_history,
    get_client_ip,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# MAIN CHAT ENDPOINT
# ──────────────────────────────────────────────────────────────

@require_POST
def chat_api(request):
    """
    AJAX endpoint — receives a user message, calls OpenRouter,
    returns AI reply.

    POST JSON body:
        message     : str   — the user's message
        session_key : str   — optional, to continue a session

    Response JSON:
        success     : bool
        reply       : str
        session_key : str
        role        : str
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    user_message = body.get('message', '').strip()
    client_key   = body.get('session_key', '')

    if not user_message:
        return JsonResponse({'success': False, 'error': 'Message cannot be empty'}, status=400)

    if len(user_message) > 1000:
        return JsonResponse({'success': False, 'error': 'Message too long (max 1000 chars)'}, status=400)

    user = request.user
    role = get_user_role(user)

    # ── Authenticated user ──────────────────────────────────
    if user.is_authenticated:
        session = _get_or_create_session(user, role, client_key)

        # Persist user message
        ChatMessage.objects.create(session=session, role='user', content=user_message)

        # Call AI with full history
        history = build_message_history(session)
        result  = call_openrouter(history, role=role)
        ai_reply = result['reply']

        # Persist AI reply
        ChatMessage.objects.create(session=session, role='assistant', content=ai_reply)

        return JsonResponse({
            'success':     True,
            'reply':       ai_reply,
            'session_key': session.session_key,
            'role':        role,
        })

    # ── Guest user (no DB session) ──────────────────────────
    result   = call_openrouter([{"role": "user", "content": user_message}], role='guest')
    ai_reply = result['reply']
    guest_key = client_key or generate_session_key()

    try:
        GuestChatLog.objects.create(
            session_key     = guest_key,
            user_message    = user_message[:500],
            assistant_reply = ai_reply[:500],
            ip_address      = get_client_ip(request),
        )
    except Exception as e:
        logger.warning(f"Guest log failed: {e}")

    return JsonResponse({
        'success':     True,
        'reply':       ai_reply,
        'session_key': guest_key,
        'role':        'guest',
    })


# ──────────────────────────────────────────────────────────────
# CLEAR SESSION
# ──────────────────────────────────────────────────────────────

@require_POST
def clear_session(request):
    """Mark a session inactive so the user starts fresh."""
    if not request.user.is_authenticated:
        return JsonResponse({'success': True})

    try:
        body = json.loads(request.body)
        key  = body.get('session_key', '')
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    if key:
        ChatSession.objects.filter(session_key=key, user=request.user).update(is_active=False)

    return JsonResponse({'success': True})


# ──────────────────────────────────────────────────────────────
# GET HISTORY  (restores chat on page reload)
# ──────────────────────────────────────────────────────────────

def get_history(request):
    """Return last 20 messages for a session (GET request)."""
    if not request.user.is_authenticated:
        return JsonResponse({'success': True, 'messages': []})

    key = request.GET.get('session_key', '')
    if not key:
        return JsonResponse({'success': True, 'messages': []})

    try:
        session  = ChatSession.objects.get(session_key=key, user=request.user, is_active=True)
        messages = session.messages.filter(role__in=['user', 'assistant']).order_by('created_at')[:20]
        data     = [{'role': m.role, 'content': m.content} for m in messages]
        return JsonResponse({'success': True, 'messages': data})
    except ChatSession.DoesNotExist:
        return JsonResponse({'success': True, 'messages': []})


# ──────────────────────────────────────────────────────────────
# STATUS / HEALTH
# ──────────────────────────────────────────────────────────────

def assistant_status(request):
    """Frontend pings this to confirm assistant is online and get role."""
    return JsonResponse({
        'online':        True,
        'role':          get_user_role(request.user),
        'authenticated': request.user.is_authenticated,
    })


# ──────────────────────────────────────────────────────────────
# PRIVATE HELPERS
# ──────────────────────────────────────────────────────────────

def _get_or_create_session(user, role, session_key=''):
    """Return existing active session or create a new one."""
    if session_key:
        try:
            return ChatSession.objects.get(session_key=session_key, user=user, is_active=True)
        except ChatSession.DoesNotExist:
            pass
    return ChatSession.objects.create(
        user=user,
        mode=role,
        session_key=generate_session_key(),
    )
    
## ─────────────────────────────────────────────────────────────────
##  MERGE THIS INTO ai_assistant/views.py  (add below existing views)
## ─────────────────────────────────────────────────────────────────

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
import json

from .utils import generate_food_item_structured, get_vendor_categories, get_user_role


@login_required
@require_POST
def generate_food_item_view(request):
    """
    POST /ai/generate-food-item/
    Body: { "prompt": "spicy paneer burger with chipotle sauce" }
    Returns: { success, item: {title, description, category, price, tags} }
              or { success: false, error: "..." }
    """
    role = get_user_role(request.user)
    if role != "vendor":
        return JsonResponse({"success": False, "error": "Only vendors can use this feature."}, status=403)

    try:
        body = json.loads(request.body)
        prompt = body.get("prompt", "").strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"success": False, "error": "Invalid request body."}, status=400)

    if not prompt:
        return JsonResponse({"success": False, "error": "Please describe the food item."}, status=400)

    # Get this vendor's existing categories for smarter suggestions
    try:
        from vendor.models import Vendor
        vendor = Vendor.objects.get(user=request.user)
        categories = get_vendor_categories(vendor)
    except Exception:
        vendor = None
        categories = []

    try:
        item = generate_food_item_structured(prompt, vendor_categories=categories)
        return JsonResponse({"success": True, "item": item})
    except ValueError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)
    except Exception as e:
        return JsonResponse({"success": False, "error": f"AI error: {str(e)}"}, status=500)


@login_required
@require_POST
def save_food_item_view(request):
    """
    POST /ai/save-food-item/
    Body: { title, description, category, price, tags }
    Saves the item to menu.FoodItem for the logged-in vendor.
    Returns: { success, food_item_id, message }
    """
    role = get_user_role(request.user)
    if role != "vendor":
        return JsonResponse({"success": False, "error": "Only vendors can use this feature."}, status=403)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"success": False, "error": "Invalid request body."}, status=400)

    required_fields = ["title", "description", "category", "price"]
    for field in required_fields:
        if not body.get(field):
            return JsonResponse({"success": False, "error": f"Missing field: {field}"}, status=400)

    try:
        from vendor.models import Vendor
        from menu.models import Category, FoodItem

        vendor = Vendor.objects.get(user=request.user)

        # Get or create category
        category_name = body["category"].strip()
        category, _ = Category.objects.get_or_create(
            vendor=vendor,
            category_name__iexact=category_name,
            defaults={"category_name": category_name}
        )

        # Create the food item
        food_item = FoodItem.objects.create(
            vendor=vendor,
            category=category,
            food_title=body["title"].strip(),
            description=body["description"].strip(),
            price=float(body["price"]),
            is_available=True,
        )

        return JsonResponse({
            "success": True,
            "food_item_id": food_item.id,
            "message": f"✅ '{food_item.food_title}' saved to your menu!",
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": f"Save failed: {str(e)}"}, status=500)
    

@login_required
@require_http_methods(["GET"])
def compare_pricing_view(request):
    """
    GET /ai/compare-pricing/
    Returns price comparison data + AI summary for the logged-in vendor.
    """
    role = get_user_role(request.user)
    if role != 'vendor':
        return JsonResponse({'success': False, 'error': 'Vendors only.'}, status=403)

    try:
        from vendor.models import Vendor
        vendor = Vendor.objects.get(user=request.user)
    except Vendor.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Vendor profile not found.'}, status=404)

    try:
        comparison_data = build_price_comparison_data(vendor)
    except Exception as e:
        logger.error(f"Price comparison error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

    if not comparison_data['items']:
        return JsonResponse({
            'success': True,
            'summary': "You don't have any menu items yet. Add some items first!",
            'data':    comparison_data,
        })

    # Ask AI to summarize
    formatted = format_comparison_for_ai(comparison_data)
    ai_prompt = f"""You are a restaurant pricing consultant.
Here is the price comparison data for a vendor:

{formatted}

Give a SHORT, actionable summary (max 5 bullet points) with:
- Which items are priced well
- Which items are too expensive vs market
- Which items are priced too low (opportunity to increase)
- 1-2 specific recommendations

Be concise, friendly, use ₹ symbol. No markdown headers."""

    result = call_openrouter(
        [{"role": "user", "content": ai_prompt}],
        role='vendor'
    )

    summary = result['reply'] if result['success'] else "⚠️ AI summary unavailable, but here's the raw data:"

    return JsonResponse({
        'success': True,
        'summary': summary,
        'data':    comparison_data,
    })