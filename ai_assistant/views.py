import json
import logging
import base64
import re

from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile

from .models import ChatSession, ChatMessage, GuestChatLog
from .utils import (
    get_user_role,
    generate_session_key,
    call_openrouter,
    build_message_history,
    get_client_ip,
)
from .vendor_utils import (
    build_price_comparison_data,
    format_comparison_for_ai,
    generate_food_item_structured,
    get_vendor_categories,
)
from .customer_utils import (
    parse_customer_intent,
    query_food_recommendations,
    format_recommendations_for_ai,
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
    ip   = get_client_ip(request)

    # ── Rate limiting (Phase 10) ────────────────────────────
    from .utils import check_rate_limit
    allowed, rate_msg = check_rate_limit(user=user, ip=ip)
    if not allowed:
        return JsonResponse({'success': False, 'error': rate_msg, 'rate_limited': True}, status=429)

    # ── Authenticated user ──────────────────────────────────
    if user.is_authenticated:
        session = _get_or_create_session(user, role, client_key)

        ChatMessage.objects.create(session=session, role='user', content=user_message)

        history = build_message_history(session)
        result  = call_openrouter(
            history, role=role,
            user=user, ip=ip, session_key=session.session_key,
            feature='chat', user_message=user_message,
        )
        ai_reply = result['reply']

        ChatMessage.objects.create(session=session, role='assistant', content=ai_reply)

        return JsonResponse({
            'success':     True,
            'reply':       ai_reply,
            'session_key': session.session_key,
            'role':        role,
        })

    # ── Guest user (no DB session) ──────────────────────────
    result    = call_openrouter(
        [{"role": "user", "content": user_message}], role='guest',
        ip=ip, feature='chat', user_message=user_message,
    )
    ai_reply  = result['reply']
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
# GET HISTORY
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


def _save_image_to_food_item(food_item, image_url, slug):
    """
    Saves an image to a FoodItem regardless of whether it is:
      - A base64 DataURL  (data:image/jpeg;base64,/9j/...)  ← from manual upload
      - A remote HTTP URL (https://image.pollinations.ai/…) ← from AI generation

    Returns True on success, False on failure (non-fatal — item is already saved).
    """
    if not image_url:
        return False

    try:
        # ── Base64 DataURL (vendor uploaded their own photo) ──────────
        if image_url.startswith('data:'):
            # Format: data:<mime>;base64,<data>
            match = re.match(r'data:(image/\w+);base64,(.+)', image_url, re.DOTALL)
            if not match:
                logger.warning(f"Unrecognised DataURL format for {food_item.food_title}")
                return False

            mime     = match.group(1)                        # e.g. image/jpeg
            raw_b64  = match.group(2).strip()
            img_data = base64.b64decode(raw_b64)

            # Derive a sensible extension from the MIME type
            ext_map  = {'image/jpeg': 'jpg', 'image/png': 'png',
                        'image/webp': 'webp', 'image/gif': 'gif'}
            ext      = ext_map.get(mime, 'jpg')
            filename = f"{slug}.{ext}"

            food_item.image.save(filename, ContentFile(img_data), save=True)
            logger.info(f"Base64 image saved for '{food_item.food_title}'")
            return True

        # ── Remote URL (AI-generated via Pollinations / Foodish) ──────
        import urllib.request
        req = urllib.request.Request(
            image_url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            img_data = resp.read()

        filename = f"{slug}.jpg"
        food_item.image.save(filename, ContentFile(img_data), save=True)
        logger.info(f"Remote image saved for '{food_item.food_title}'")
        return True

    except Exception as e:
        logger.warning(f"Image save failed for '{food_item.food_title}': {e}")
        return False


# ──────────────────────────────────────────────────────────────
# GENERATE FOOD ITEM
# ──────────────────────────────────────────────────────────────

@login_required
@require_POST
def generate_food_item_view(request):
    """
    POST /ai/generate-food-item/
    Body: { "prompt": "spicy paneer burger with chipotle sauce" }
    Returns: { success, item: {title, description, category, price, tags} }
    """
    role = get_user_role(request.user)
    if role != 'vendor':
        return JsonResponse({'success': False, 'error': 'Only vendors can use this feature.'}, status=403)

    try:
        body   = json.loads(request.body)
        prompt = body.get('prompt', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'error': 'Invalid request body.'}, status=400)

    if not prompt:
        return JsonResponse({'success': False, 'error': 'Please describe the food item.'}, status=400)

    try:
        from vendor.models import Vendor
        vendor     = Vendor.objects.get(user=request.user)
        categories = get_vendor_categories(vendor)
    except Exception:
        vendor     = None
        categories = []

    try:
        item = generate_food_item_structured(prompt, vendor_categories=categories)
        return JsonResponse({'success': True, 'item': item})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'AI error: {str(e)}'}, status=500)


# ──────────────────────────────────────────────────────────────
# SAVE FOOD ITEM
# ──────────────────────────────────────────────────────────────

@login_required
@require_POST
def save_food_item_view(request):
    """
    POST /ai/save-food-item/
    Accepts image_url as either:
      - A base64 DataURL  (vendor uploaded their own photo)
      - A remote HTTP URL (AI-generated image)
      - Empty string      (no image)
    """
    role = get_user_role(request.user)
    if role != 'vendor':
        return JsonResponse({'success': False, 'error': 'Only vendors can use this feature.'}, status=403)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'error': 'Invalid request body.'}, status=400)

    # Validate required fields
    for field in ['title', 'description', 'category', 'price']:
        if not body.get(field) and body.get(field) != 0:
            return JsonResponse({'success': False, 'error': f'Missing required field: {field}'}, status=400)

    try:
        from vendor.models import Vendor
        from menu.models import Category, FoodItem
        from django.utils.text import slugify

        vendor = Vendor.objects.get(user=request.user)

        # ── Category: find existing or create ──────────────────
        category_name = body['category'].strip()
        category = Category.objects.filter(
            vendor=vendor,
            category_name__iexact=category_name,
        ).first()

        if not category:
            base_slug = slugify(category_name)
            slug      = base_slug
            counter   = 1
            while Category.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            category = Category.objects.create(
                vendor=vendor,
                category_name=category_name,
                slug=slug,
            )

        # ── FoodItem slug ───────────────────────────────────────
        food_title = body['title'].strip()
        base_slug  = slugify(food_title)
        slug       = base_slug
        counter    = 1
        while FoodItem.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        # ── Create FoodItem (no image yet) ──────────────────────
        food_item = FoodItem.objects.create(
            vendor       = vendor,
            category     = category,
            food_title   = food_title,
            description  = body['description'].strip(),
            price        = float(body['price']),
            slug         = slug,
            is_available = True,
        )

        # ── Save image (base64 OR remote URL) ───────────────────
        image_url = body.get('image_url', '').strip()
        has_image = _save_image_to_food_item(food_item, image_url, slug)

        return JsonResponse({
            'success':      True,
            'food_item_id': food_item.id,
            'message':      f"✅ '{food_item.food_title}' saved to your menu!",
            'has_image':    has_image,
        })

    except Exception as e:
        logger.error(f"Save food item error: {e}")
        return JsonResponse({'success': False, 'error': f'Save failed: {str(e)}'}, status=500)


# ──────────────────────────────────────────────────────────────
# PRICE COMPARISON
# ──────────────────────────────────────────────────────────────

@login_required
@require_http_methods(['GET'])
def compare_pricing_view(request):
    """
    GET /ai/compare-pricing/
    Returns price comparison data + AI summary for the logged-in vendor.

    Always returns success:true so the frontend can show the table even
    when the AI summary call fails — the summary field will explain why.
    """
    role = get_user_role(request.user)
    if role != 'vendor':
        return JsonResponse({'success': False, 'error': 'Vendors only.'}, status=403)

    try:
        from vendor.models import Vendor
        vendor = Vendor.objects.get(user=request.user)
    except Vendor.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Vendor profile not found.'}, status=404)

    # ── Build comparison data ───────────────────────────────────
    try:
        comparison_data = build_price_comparison_data(vendor)
    except Exception as e:
        logger.error(f"Price comparison build error: {e}")
        return JsonResponse({'success': False, 'error': f'Could not load your pricing data: {str(e)}'}, status=500)

    # ── No menu items yet ───────────────────────────────────────
    if not comparison_data.get('items'):
        return JsonResponse({
            'success': True,
            'summary': "You don't have any menu items yet. Add some items and come back!",
            'data':    comparison_data,
        })

    # ── No competitor data at all ───────────────────────────────
    has_competitor_data = any(
        item.get('competitor_avg') is not None
        for item in comparison_data['items']
    )
    if not has_competitor_data:
        item_count = len(comparison_data['items'])
        return JsonResponse({
            'success': True,
            'summary': (
                f"📋 You have {item_count} menu item{'s' if item_count != 1 else ''}. "
                "No other vendors in your city have matching items yet, so there's nothing to compare. "
                "Keep building your menu — comparison data will appear as more vendors join your area!"
            ),
            'data': comparison_data,
        })

    # ── Ask AI to summarise ─────────────────────────────────────
    formatted = format_comparison_for_ai(comparison_data)
    ai_prompt = f"""You are a restaurant pricing consultant.
Here is the price comparison data for a vendor:

{formatted}

Give a SHORT, actionable summary (max 5 bullet points) with:
- Which items are priced well
- Which items are too expensive vs the market
- Which items are priced too low (opportunity to increase)
- 1-2 specific recommendations

Be concise, friendly, use ₹ symbol. No markdown headers."""

    result = call_openrouter(
        [{'role': 'user', 'content': ai_prompt}],
        role='vendor',
    )

    if result['success'] and result['reply']:
        summary = result['reply']
    else:
        # AI failed — build a plain-text summary from the raw data ourselves
        # so the vendor still gets something useful
        expensive = [i['title'] for i in comparison_data['items'] if i.get('status') == 'expensive']
        cheap     = [i['title'] for i in comparison_data['items'] if i.get('status') == 'cheap']
        ok        = [i['title'] for i in comparison_data['items'] if i.get('status') == 'competitive']

        lines = ['📊 Pricing summary (AI unavailable — showing raw analysis):']
        if ok:
            lines.append(f"✅ Competitively priced: {', '.join(ok)}")
        if expensive:
            lines.append(f"🔴 Priced above market: {', '.join(expensive)} — consider reducing slightly")
        if cheap:
            lines.append(f"🟡 Priced below market: {', '.join(cheap)} — you may have room to increase")
        if not (ok or expensive or cheap):
            lines.append("No matching competitor items found for detailed analysis.")

        summary = '\n'.join(lines)
        logger.warning(f"AI summary failed for vendor {vendor.id}, using fallback. Error: {result.get('error')}")

    return JsonResponse({
        'success': True,
        'summary': summary,
        'data':    comparison_data,
    })
# ──────────────────────────────────────────────────────────────
# PHASE 5 — CUSTOMER MOOD-BASED FOOD RECOMMENDATIONS
# ──────────────────────────────────────────────────────────────

@require_http_methods(['GET'])
def recommend_food_view(request):
    message = request.GET.get('q', '').strip()
    if not message:
        return JsonResponse(
            {'success': False, 'error': 'Please send a message to get recommendations.'},
            status=400,
        )

    if len(message) > 500:
        return JsonResponse(
            {'success': False, 'error': 'Message too long (max 500 chars).'},
            status=400,
        )

    intent = parse_customer_intent(message)

    if not intent['is_food_request']:
        return JsonResponse({
            'success': True,
            'intro':   "I'm not sure what you're looking for 😊 Tell me what you're craving or how you're feeling, and I'll find the perfect dish!",
            'items':   [],
            'intent':  intent,
        })

    user  = request.user if request.user.is_authenticated else None
    items = query_food_recommendations(intent, customer_user=user, limit=5)

    if not items:
        return JsonResponse({
            'success': True,
            'intro':   (
                "😕 I couldn't find matching dishes right now — "
                "our vendors are still growing! "
                "Try browsing all restaurants or search by name."
            ),
            'items':   [],
            'intent':  intent,
        })

    formatted = format_recommendations_for_ai(items, intent)
    ai_prompt = (
        f"You are a friendly food assistant for FoodOnline.\n"
        f"Here is what the customer said and the top matching dishes:\n\n"
        f"{formatted}\n\n"
        f"Write a SHORT, warm, enthusiastic 2-3 sentence intro message that:\n"
        f"- Acknowledges their mood/craving\n"
        f"- Teases the recommendations below\n"
        f"- Uses 1-2 food emojis\n"
        f"Do NOT list the dishes — the cards handle that. "
        f"Keep it under 60 words. No markdown."
    )

    result = call_openrouter(
        [{'role': 'user', 'content': ai_prompt}],
        role='customer',
    )

    if result['success'] and result['reply']:
        intro = result['reply']
    else:
        moods    = intent.get('moods', [])
        mood_str = moods[0] if moods else 'your craving'
        intro    = (
            f"🍽️ Perfect! I found some great options for your {mood_str} mood. "
            f"Here are my top picks just for you!"
        )

    return JsonResponse({
        'success': True,
        'intro':   intro,
        'items':   items,
        'intent':  intent,
    })
    
# ──────────────────────────────────────────────────────────────
# PHASE — ORDER TRACKING
# ──────────────────────────────────────────────────────────────

@login_required
@require_http_methods(['GET'])
def order_tracking_view(request):
    """
    GET /ai/orders/
    Returns last 5 orders for the logged-in customer with
    status, timeline, items, and vendor contact info.
    """
    from .customer_utils import get_customer_orders
    role = get_user_role(request.user)
    if role != 'customer':
        return JsonResponse({'success': False, 'error': 'Customers only.'}, status=403)

    orders = get_customer_orders(request.user, limit=5)

    if not orders:
        return JsonResponse({
            'success': True,
            'message': "You haven't placed any orders yet. Browse restaurants and order something delicious! 🍽️",
            'orders':  [],
        })

    return JsonResponse({'success': True, 'orders': orders})


# ──────────────────────────────────────────────────────────────
# PHASE — SMART REORDER SUGGESTIONS
# ──────────────────────────────────────────────────────────────

@login_required
@require_http_methods(['GET'])
def reorder_suggestions_view(request):
    """
    GET /ai/reorder/
    Returns top 4 previously ordered items that are still available.
    """
    from .customer_utils import get_reorder_suggestions
    role = get_user_role(request.user)
    if role != 'customer':
        return JsonResponse({'success': False, 'error': 'Customers only.'}, status=403)

    suggestions = get_reorder_suggestions(request.user, limit=4)

    if not suggestions:
        return JsonResponse({
            'success': True,
            'message': "No reorder suggestions yet — place your first order and we'll remember your favourites! 🧠",
            'items':   [],
        })

    return JsonResponse({'success': True, 'items': suggestions})


# ──────────────────────────────────────────────────────────────
# PHASE 6 — NEARBY RESTAURANT DISCOVERY
# ──────────────────────────────────────────────────────────────

@require_http_methods(['GET'])
def nearby_restaurants_view(request):
    """
    GET /ai/nearby/
    Returns approved vendors near the customer.
    Works for both authenticated and guest users.
    """
    from .customer_utils import get_nearby_vendors

    user    = request.user if request.user.is_authenticated else None
    vendors = get_nearby_vendors(user, limit=6)

    if not vendors:
        return JsonResponse({
            'success': True,
            'message': "No restaurants found yet. Check back soon — more vendors are joining! 🍽️",
            'vendors': [],
        })

    return JsonResponse({'success': True, 'vendors': vendors})

# ──────────────────────────────────────────────────────────────
# PHASE 7 — VENDOR CONTACT INFO
# ──────────────────────────────────────────────────────────────

@require_http_methods(['GET'])
def vendor_info_view(request, vendor_id):
    """
    GET /ai/vendor-info/<vendor_id>/
    Returns contact info + opening hours for a vendor.
    Works for authenticated and guest users.
    """
    from vendor.models import Vendor, OpeningHour
    from vendor.utils import is_open_now

    try:
        vendor = Vendor.objects.select_related(
            'user', 'user_profile'
        ).get(id=vendor_id, is_approved=True)
    except Vendor.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Vendor not found.'}, status=404)

    # Opening hours — all 7 days
    hours = OpeningHour.objects.filter(vendor=vendor).order_by('day')
    DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    hours_list = []
    for h in hours:
        hours_list.append({
            'day':       DAY_NAMES[h.day - 1] if 1 <= h.day <= 7 else f'Day {h.day}',
            'is_closed': h.is_closed,
            'from_hour': h.from_hour if not h.is_closed else None,
            'to_hour':   h.to_hour   if not h.is_closed else None,
        })

    profile = vendor.user_profile

    return JsonResponse({
        'success': True,
        'vendor': {
            'id':        vendor.id,
            'name':      vendor.vendor_name,
            'slug':      vendor.vendor_slug,
            'phone':     vendor.user.phone_number or '',
            'email':     vendor.user.email or '',
            'address':   profile.address or '',
            'city':      profile.city or '',
            'state':     profile.state or '',
            'pincode':   profile.pincode or '',
            'is_open':   is_open_now(vendor),
            'hours':     hours_list,
        },
    })
    
    
# ──────────────────────────────────────────────────────────────
# PROACTIVE DEAL NUDGE
# ──────────────────────────────────────────────────────────────

@require_http_methods(['GET'])
def proactive_nudge_view(request):
    """
    GET /ai/nudge/
    Returns a personalised nudge message for returning customers.
    Returns null message for guests, vendors, or new customers.
    Silent — never errors, always returns success:true.
    """
    from .customer_utils import get_proactive_nudge

    # Only for authenticated customers
    role = get_user_role(request.user)
    if role != 'customer':
        return JsonResponse({'success': True, 'message': None})

    message = get_proactive_nudge(request.user)
    return JsonResponse({'success': True, 'message': message})