# ai_assistant/customer_utils.py
#
# Phase 5 — Customer mood/craving food recommendations.
#
# Flow:
#   1. parse_customer_intent(message)
#      → returns { mood, keywords, dietary, cuisine }
#   2. query_food_recommendations(intent, customer_user=None)
#      → queries FoodItem + Vendor, returns up to 5 ranked items
#   3. format_recommendations_for_ai(items, intent)
#      → builds a compact text block for the AI summary prompt
#
# The view calls (2) for the card data and (3) + call_openrouter for
# the conversational reply that appears above the cards.

import logging
from django.db.models import Q
from menu.models import FoodItem
from vendor.models import Vendor
from accounts.models import UserProfile

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# MOOD / KEYWORD MAPS
# ══════════════════════════════════════════════════════════════════

# Maps mood phrases → food keywords that match FoodItem titles/descriptions
MOOD_TO_KEYWORDS = {
    # Emotional states
    'happy':      ['biryani', 'pizza', 'burger', 'cake', 'dessert', 'sweet'],
    'sad':        ['chocolate', 'ice cream', 'cake', 'pasta', 'comfort', 'halwa'],
    'stressed':   ['pizza', 'burger', 'chocolate', 'fries', 'snack', 'roll'],
    'tired':      ['coffee', 'tea', 'juice', 'smoothie', 'light', 'salad'],
    'excited':    ['biryani', 'pizza', 'sushi', 'burger', 'grill', 'bbq'],
    'bored':      ['snack', 'fries', 'sandwich', 'roll', 'chaat', 'pakoda'],
    'romantic':   ['pasta', 'pizza', 'dessert', 'chocolate', 'cake', 'starter'],
    'hungover':   ['biryani', 'maggi', 'soup', 'paratha', 'chai', 'bread'],

    # Craving types
    'spicy':      ['spicy', 'chilli', 'hot', 'pepper', 'masala', 'tikka', 'tandoori'],
    'sweet':      ['dessert', 'cake', 'halwa', 'kheer', 'gulab', 'ladoo', 'ice cream', 'sweet'],
    'salty':      ['chaat', 'fries', 'chips', 'popcorn', 'pretzel', 'pickle'],
    'sour':       ['tamarind', 'lemon', 'chaat', 'rasam', 'imli', 'tangy'],
    'crispy':     ['fries', 'pakoda', 'samosa', 'fried', 'crispy', 'fritter', 'bhajji'],
    'creamy':     ['pasta', 'paneer', 'butter', 'cream', 'malai', 'korma', 'alfredo'],
    'light':      ['salad', 'soup', 'grilled', 'steamed', 'dal', 'khichdi', 'oats'],
    'heavy':      ['biryani', 'mutton', 'butter chicken', 'naan', 'lasagna', 'kebab'],

    # Health intent
    'healthy':    ['salad', 'grilled', 'steamed', 'oats', 'smoothie', 'fruit', 'dal', 'multigrain'],
    'diet':       ['salad', 'grilled', 'low calorie', 'soup', 'steamed', 'oats', 'fruit'],
    'protein':    ['chicken', 'egg', 'paneer', 'dal', 'fish', 'lentil', 'soya'],
    'vegan':      ['vegan', 'plant', 'tofu', 'salad', 'dal', 'vegetable', 'fruit'],
    'vegetarian': ['paneer', 'dal', 'vegetable', 'aloo', 'palak', 'rajma', 'chole'],

    # Cuisine
    'indian':     ['biryani', 'dal', 'roti', 'paneer', 'curry', 'sabzi', 'naan'],
    'chinese':    ['noodle', 'fried rice', 'manchurian', 'chowmein', 'dumpling', 'spring roll'],
    'italian':    ['pizza', 'pasta', 'risotto', 'lasagna', 'bruschetta'],
    'mexican':    ['taco', 'burrito', 'nachos', 'quesadilla', 'wrap'],
    'south indian': ['dosa', 'idli', 'uttapam', 'vada', 'sambar', 'rasam'],

    # Time / occasion
    'breakfast':  ['paratha', 'idli', 'dosa', 'oats', 'egg', 'toast', 'poha', 'upma'],
    'lunch':      ['rice', 'dal', 'roti', 'curry', 'sabzi', 'biryani', 'thali'],
    'dinner':     ['biryani', 'naan', 'paneer', 'chicken', 'kebab', 'pasta'],
    'snack':      ['samosa', 'pakoda', 'sandwich', 'roll', 'chaat', 'fries', 'bhel'],
    'midnight':   ['maggi', 'sandwich', 'pizza', 'pasta', 'noodle', 'instant'],
    'party':      ['pizza', 'burger', 'fries', 'cake', 'mocktail', 'kebab', 'finger food'],
}

# Dietary filter phrases → used to add a FoodItem queryset filter
DIETARY_TRIGGERS = {
    'vegan':      ['vegan'],
    'vegetarian': ['veg', 'vegetarian', 'no meat', 'no chicken', 'no fish'],
    'non-veg':    ['non veg', 'chicken', 'mutton', 'fish', 'prawn', 'egg', 'meat'],
}


# ══════════════════════════════════════════════════════════════════
# INTENT PARSER
# ══════════════════════════════════════════════════════════════════

def parse_customer_intent(message: str) -> dict:
    """
    Parse a free-text customer message into a structured intent dict.

    Returns:
        {
            'raw':      str,              # original message
            'moods':    list[str],        # matched mood keys
            'keywords': list[str],        # food keyword pool (for DB query)
            'dietary':  str | None,       # 'vegan' | 'vegetarian' | 'non-veg' | None
            'is_food_request': bool,      # False for pure greetings/non-food
        }
    """
    lower = message.lower()

    # ── Detect dietary preference ────────────────────────────────
    dietary = None
    for pref, triggers in DIETARY_TRIGGERS.items():
        if any(t in lower for t in triggers):
            dietary = pref
            break

    # ── Match moods/cravings ─────────────────────────────────────
    matched_moods = []
    keyword_pool  = []

    for mood, keywords in MOOD_TO_KEYWORDS.items():
        # Check mood word itself OR any of its food keywords in the message
        mood_words = mood.replace('_', ' ').split()
        if any(mw in lower for mw in mood_words) or any(kw in lower for kw in keywords):
            matched_moods.append(mood)
            keyword_pool.extend(keywords)

    # De-duplicate while preserving order
    seen = set()
    unique_keywords = []
    for kw in keyword_pool:
        if kw not in seen:
            seen.add(kw)
            unique_keywords.append(kw)

    # ── Is this actually a food request? ─────────────────────────
    # Treat it as a food request if we matched any mood/keyword,
    # OR if the message contains direct food/order words.
    FOOD_SIGNAL_WORDS = [
        'food', 'eat', 'hungry', 'order', 'craving', 'want', 'meal',
        'restaurant', 'dish', 'recommend', 'suggest', 'find', 'show',
        'mood', 'feeling', 'feel like', 'something', 'any', 'what',
    ]
    has_food_signal = any(w in lower for w in FOOD_SIGNAL_WORDS)
    is_food_request = bool(matched_moods) or has_food_signal

    return {
        'raw':             message,
        'moods':           matched_moods,
        'keywords':        unique_keywords,
        'dietary':         dietary,
        'is_food_request': is_food_request,
    }


# ══════════════════════════════════════════════════════════════════
# FOOD ITEM QUERY
# ══════════════════════════════════════════════════════════════════

def query_food_recommendations(intent: dict, customer_user=None, limit: int = 5) -> list:
    """
    Query available FoodItems based on parsed intent keywords.
    Optionally biases toward vendors in the customer's city.

    Returns a list of dicts (serialisable, safe for JSON response):
    [
      {
        'id':          int,
        'food_title':  str,
        'description': str,
        'price':       float,
        'category':    str,
        'vendor_name': str,
        'vendor_id':   int,
        'image_url':   str | None,
        'slug':        str,
        'match_reason': str,   # human-readable why this was picked
      },
      ...
    ]
    """
    keywords = intent.get('keywords', [])
    dietary  = intent.get('dietary')

    # ── Base queryset — only approved vendors, available items ───
    qs = FoodItem.objects.filter(
        is_available=True,
        vendor__is_approved=True,
    ).select_related('vendor', 'category')

    # ── Keyword filter (OR across food_title + description) ──────
    if keywords:
        kw_q = Q()
        for kw in keywords[:10]:   # cap at 10 to keep the query sane
            kw_q |= Q(food_title__icontains=kw) | Q(description__icontains=kw)
        qs = qs.filter(kw_q)

    # ── City bias — prefer same city as customer ─────────────────
    customer_city = _get_customer_city(customer_user)
    if customer_city:
        city_vendor_ids = UserProfile.objects.filter(
            city__icontains=customer_city.split()[-1]
        ).values_list('user_id', flat=True)

        city_qs  = qs.filter(vendor__user_id__in=city_vendor_ids)
        other_qs = qs.exclude(vendor__user_id__in=city_vendor_ids)

        # Merge: city-first, then others, dedup by id
        items = list(city_qs[:limit]) + list(other_qs[:limit])
        seen_ids = set()
        deduped  = []
        for item in items:
            if item.id not in seen_ids:
                seen_ids.add(item.id)
                deduped.append(item)
        qs_final = deduped[:limit]
    else:
        qs_final = list(qs[:limit])

    # ── Serialise ────────────────────────────────────────────────
    results = []
    for item in qs_final:
        image_url = None
        if item.image:
            try:
                image_url = item.image.url
            except Exception:
                pass

        # Build a short human-readable reason
        matched_kws = [
            kw for kw in keywords
            if kw.lower() in item.food_title.lower()
            or kw.lower() in (item.description or '').lower()
        ]
        reason = f"Matches: {', '.join(matched_kws[:3])}" if matched_kws else "Popular item"

        results.append({
            'id':           item.id,
            'food_title':   item.food_title,
            'description':  item.description or '',
            'price':        float(item.price),
            'category':     item.category.category_name if item.category else '',
            'vendor_name':  item.vendor.vendor_name,
            'vendor_id':    item.vendor.id,
            'vendor_slug':  item.vendor.vendor_slug,
            'image_url':    image_url,
            'slug':         item.slug,
            'match_reason': reason,
        })

    return results


def _get_customer_city(user) -> str | None:
    """Return the city of the logged-in customer, or None."""
    if not user or not user.is_authenticated:
        return None
    try:
        return UserProfile.objects.get(user=user).city
    except UserProfile.DoesNotExist:
        return None


# ══════════════════════════════════════════════════════════════════
# AI PROMPT FORMATTER
# ══════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════
# PHASE — ORDER TRACKING
# ══════════════════════════════════════════════════════════════════

# Status → emoji + human label
ORDER_STATUS_META = {
    'New':       {'emoji': '🆕', 'label': 'Order Placed',    'color': '#3498db'},
    'Accepted':  {'emoji': '👨‍🍳', 'label': 'Being Prepared',  'color': '#e67e22'},
    'Completed': {'emoji': '✅', 'label': 'Delivered',        'color': '#27ae60'},
    'Cancelled': {'emoji': '❌', 'label': 'Cancelled',        'color': '#c0392b'},
}

# Timeline steps per status
ORDER_TIMELINE = {
    'New':       ['Order Placed 🆕', 'Waiting for vendor...', '', ''],
    'Accepted':  ['Order Placed 🆕', 'Accepted by vendor 👨‍🍳', 'Being prepared...', ''],
    'Completed': ['Order Placed 🆕', 'Accepted 👨‍🍳', 'Prepared ✅', 'Delivered 🎉'],
    'Cancelled': ['Order Placed 🆕', 'Cancelled ❌', '', ''],
}


def get_customer_orders(user, limit=5):
    """
    Fetch last `limit` completed orders for a customer.
    Returns a list of serialisable dicts.
    """
    from orders.models import Order, OrderedFood

    orders = (
        Order.objects
        .filter(user=user, is_ordered=True)
        .prefetch_related('vendors', 'orderedfood_set__fooditem__vendor')
        .order_by('-created_at')[:limit]
    )

    result = []
    for order in orders:
        # Collect items
        items = []
        for of in order.orderedfood_set.all():
            items.append({
                'food_title': of.fooditem.food_title,
                'quantity':   of.quantity,
                'price':      float(of.price),
                'amount':     float(of.amount),
                'vendor_name': of.fooditem.vendor.vendor_name,
                'vendor_slug': of.fooditem.vendor.vendor_slug,
                'vendor_email': of.fooditem.vendor.user.email,
                'vendor_phone': of.fooditem.vendor.user.phone_number or '',
            })

        # Group items by vendor
        vendors = {}
        for it in items:
            vname = it['vendor_name']
            if vname not in vendors:
                vendors[vname] = {
                    'name':  vname,
                    'slug':  it['vendor_slug'],
                    'email': it['vendor_email'],
                    'phone': it['vendor_phone'],
                    'items': [],
                }
            vendors[vname]['items'].append(it)

        meta = ORDER_STATUS_META.get(order.status, ORDER_STATUS_META['New'])
        timeline = ORDER_TIMELINE.get(order.status, ORDER_TIMELINE['New'])

        result.append({
            'order_number':  order.order_number,
            'status':        order.status,
            'status_emoji':  meta['emoji'],
            'status_label':  meta['label'],
            'status_color':  meta['color'],
            'timeline':      timeline,
            'total':         float(order.total),
            'payment_method': order.payment_method,
            'payment_id':    order.payment.transaction_id if order.payment else '',
            'created_at':    order.created_at.strftime('%d %b %Y, %I:%M %p'),
            'vendors':       list(vendors.values()),
            'items':         items,
        })

    return result


# ══════════════════════════════════════════════════════════════════
# PHASE — SMART REORDER SUGGESTIONS
# ══════════════════════════════════════════════════════════════════

# Fun copy pool — indexed by order_count so same item always gets same text
REORDER_COPY = [
    ("Your usual? We saved you a seat 🪑",           "You've ordered this before. Clearly you have taste."),
    ("Back again? Your taste buds have memory 🧠",   "This one keeps calling your name. We don't blame you."),
    ("You had this {n} times 👀 Coincidence? Nope.", "Some things are just worth repeating."),
    ("A certified favourite 🏅",                     "Ordered {n} times and counting. A legend on your plate."),
    ("Your go-to comfort food 🛋️",                   "When in doubt, you always know what to pick."),
    ("The one you keep coming back to 🔄",           "Loyalty looks good on you — and tastes even better."),
    ("Old reliable 💪",                              "No need to overthink it. You already know this one slaps."),
    ("Tried. Tested. Trusted. 🎯",                  "Your order history doesn't lie — this one's a winner."),
]


def get_reorder_suggestions(user, limit=4):
    """
    Analyse past orders → find most-ordered food items →
    check if they're still available → return suggestion cards.
    """
    from orders.models import OrderedFood
    from django.db.models import Sum

    # Aggregate order counts per food item
    top_items = (
        OrderedFood.objects
        .filter(user=user)
        .values('fooditem_id')
        .annotate(total_qty=Sum('quantity'))
        .order_by('-total_qty')[:limit * 2]   # fetch extra, some may be unavailable
    )

    from menu.models import FoodItem
    suggestions = []

    for entry in top_items:
        if len(suggestions) >= limit:
            break
        try:
            food = FoodItem.objects.select_related(
                'vendor', 'category'
            ).get(
                id=entry['fooditem_id'],
                is_available=True,
                vendor__is_approved=True,
            )
        except FoodItem.DoesNotExist:
            continue   # item removed or vendor unapproved — skip

        count = entry['total_qty']
        idx   = len(suggestions) % len(REORDER_COPY)
        title_raw, sub_raw = REORDER_COPY[idx]
        title = title_raw.replace('{n}', str(count))
        sub   = sub_raw.replace('{n}', str(count))

        image_url = None
        if food.image:
            try:
                image_url = food.image.url
            except Exception:
                pass

        suggestions.append({
            'id':           food.id,
            'food_title':   food.food_title,
            'description':  food.description or '',
            'price':        float(food.price),
            'category':     food.category.category_name if food.category else '',
            'vendor_name':  food.vendor.vendor_name,
            'vendor_slug':  food.vendor.vendor_slug,
            'image_url':    image_url,
            'slug':         food.slug,
            'order_count':  count,
            'copy_title':   title,
            'copy_sub':     sub,
        })

    return suggestions


def format_recommendations_for_ai(items: list, intent: dict) -> str:
    """
    Build a compact text block describing the recommendations so the AI
    can write a warm, personalised intro message above the cards.
    """
    moods    = intent.get('moods', [])
    dietary  = intent.get('dietary')
    raw      = intent.get('raw', '')

    mood_str    = ', '.join(moods[:3]) if moods else 'your craving'
    dietary_str = f" ({dietary})" if dietary else ""

    lines = [
        f"Customer said: \"{raw}\"",
        f"Detected mood/craving: {mood_str}{dietary_str}",
        "",
        f"Top {len(items)} recommended items:",
    ]
    for i, item in enumerate(items, 1):
        lines.append(
            f"{i}. {item['food_title']} — ₹{item['price']:.0f} "
            f"| {item['vendor_name']} | {item['category']}"
        )

    return "\n".join(lines)

# ══════════════════════════════════════════════════════════════════
# PHASE 6 — NEARBY RESTAURANT DISCOVERY
# ══════════════════════════════════════════════════════════════════

def get_nearby_vendors(user, limit=6):
    """
    Returns approved vendors sorted by:
      1. Distance from customer (if customer has GIS location)
      2. City match (if no GIS location)
      3. All approved vendors (final fallback)
    """
    from vendor.models import Vendor
    from django.contrib.gis.db.models.functions import Distance
    from django.contrib.gis.measure import D

    base_qs = Vendor.objects.filter(
        is_approved=True
    ).select_related('user_profile', 'user')

    # ── Get customer location ────────────────────────────────────
    customer_location = None
    customer_city     = None
    if user and user.is_authenticated:
        try:
            profile = UserProfile.objects.get(user=user)
            customer_city     = profile.city
            customer_location = profile.location
        except UserProfile.DoesNotExist:
            pass

    results = []

    # ── Strategy 1: GIS distance ─────────────────────────────────
    if customer_location:
        vendors = (
            base_qs
            .filter(user_profile__location__isnull=False)
            .annotate(distance=Distance('user_profile__location', customer_location))
            .order_by('distance')[:limit]
        )
        for v in vendors:
            dist_km = round(v.distance.km, 1)
            dist_str = 'Nearby 📍' if dist_km < 1 else f'{dist_km} km away'
            results.append(_serialize_vendor(v, distance_str=dist_str))

    # ── Strategy 2: City match fallback ──────────────────────────
    if not results and customer_city:
        vendors = base_qs.filter(
            user_profile__city__icontains=customer_city.strip()
        )[:limit]
        for v in vendors:
            results.append(_serialize_vendor(v, distance_str=f'In {customer_city}'))

    # ── Strategy 3: All approved vendors ─────────────────────────
    if not results:
        vendors = base_qs.order_by('-created_at')[:limit]
        for v in vendors:
            results.append(_serialize_vendor(v, distance_str=''))

    return results


def _serialize_vendor(vendor, distance_str=''):
    """Serialise a Vendor instance to a JSON-safe dict."""
    from menu.models import Category

    # Cover photo from user_profile
    cover_url = None
    try:
        if vendor.user_profile.cover_photo:
            cover_url = vendor.user_profile.cover_photo.url
    except Exception:
        pass

    # Profile picture as fallback
    profile_url = None
    try:
        if vendor.user_profile.profile_picture:
            profile_url = vendor.user_profile.profile_picture.url
    except Exception:
        pass

    # Cuisine tags — top 4 category names for this vendor
    categories = list(
        Category.objects.filter(vendor=vendor)
        .values_list('category_name', flat=True)[:4]
    )

    return {
        'id':           vendor.id,
        'name':         vendor.vendor_name,
        'slug':         vendor.vendor_slug,
        'cover_url':    cover_url,
        'profile_url':  profile_url,
        'city':         vendor.user_profile.city or '',
        'distance_str': distance_str,
        'categories':   categories,
    }