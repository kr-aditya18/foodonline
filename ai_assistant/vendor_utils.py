# ai_assistant/vendor_utils.py
#
# All vendor-side helper functions:
#   - Food item generation (Phase 2)
#   - Category lookup (Phase 2)
#   - Competitor price comparison (Phase 3)
#
# Previously split across utils.py (generate_food_item_structured, get_vendor_categories)
# and utils_phase3.py (everything else). Now unified here.

import json
import re
import logging
import requests

from django.conf import settings

from menu.models import FoodItem, Category
from vendor.models import Vendor
from accounts.models import UserProfile
from django.db.models import Q
logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


# ══════════════════════════════════════════════════════════════════
# PHASE 2 — FOOD ITEM GENERATOR
# ══════════════════════════════════════════════════════════════════

def get_vendor_categories(vendor):
    """Return a list of existing category names for the given vendor."""
    try:
        return list(
            Category.objects.filter(vendor=vendor).values_list("category_name", flat=True)
        )
    except Exception:
        return []


def get_market_price_hint(user_prompt):
    """
    Query DB for similar food items and return a price hint string for the AI prompt.
    Uses same word-overlap logic as Phase 3 competitor matching.
    """
    try:
        words = [w for w in user_prompt.lower().split() if len(w) > 3]
        if not words:
            return ""

        kw_q = Q()
        for w in words[:5]:
            kw_q |= Q(food_title__icontains=w)

        similar = FoodItem.objects.filter(
            kw_q,
            is_available=True,
            vendor__is_approved=True,
        ).values_list('price', flat=True)[:20]

        if not similar:
            return ""

        prices = [float(p) for p in similar]
        avg    = round(sum(prices) / len(prices), 0)
        mn     = round(min(prices), 0)
        mx     = round(max(prices), 0)
        count  = len(prices)

        return (
            f"Similar items on FoodOnline: avg ₹{avg:.0f} "
            f"(min ₹{mn:.0f}, max ₹{mx:.0f}) from {count} listing(s). "
            f"Suggest a competitive price in this range."
        )
    except Exception:
        return ""


def generate_food_item_structured(user_prompt, vendor_categories=None):
    """
    Ask the AI to generate a structured food menu item from a natural-language prompt.
    Returns a dict: {title, description, category, price, tags} or raises ValueError.

    Calls OpenRouter directly with a strict JSON-only system prompt so the
    vendor markdown prompt cannot bleed into the output.
    """
    category_hint = ""
    if vendor_categories:
        names = ", ".join(vendor_categories)
        category_hint = (
            f"The vendor already has these categories: {names}. "
            "Reuse an existing one if it fits, otherwise suggest a new one."
        )

    price_hint = get_market_price_hint(user_prompt)

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
{price_hint if price_hint else "Prices should be realistic for an Indian online food delivery platform (₹50–₹800 range)."}
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

    MODELS = [
        "openrouter/free",
        "google/gemma-3n-e4b-it:free",
        "arcee-ai/trinity-large-preview:free",
        "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
    ]

    raw = None
    for model in MODELS:
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
            logger.error(f"Food gen error ({model}): {e}")
            continue

    if not raw:
        raise ValueError("All models failed to generate food item.")

    # Strip markdown fences if a model misbehaves
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


# ══════════════════════════════════════════════════════════════════
# PHASE 3 — COMPETITOR PRICE COMPARISON
# ══════════════════════════════════════════════════════════════════

def get_vendor_city(vendor):
    """Get vendor's city from their UserProfile."""
    try:
        profile = UserProfile.objects.get(user=vendor.user)
        return profile.city
    except UserProfile.DoesNotExist:
        return None


def get_vendor_items(vendor):
    """Return all available food items for a vendor as a list of dicts."""
    return list(
        FoodItem.objects.filter(vendor=vendor, is_available=True)
        .select_related('category')
        .values('food_title', 'price', 'category__category_name')
    )


def get_competitor_prices(vendor, city=None):
    """
    Build a price map for available items from all other approved vendors.
    Optionally filtered to the same city.

    Returns:
        dict — { food_title_lower: { min, max, avg, count } }
    """
    other_vendors = Vendor.objects.filter(is_approved=True).exclude(pk=vendor.pk)

    if city:
        city_user_ids = UserProfile.objects.filter(
            city__icontains=city.split()[-1]   # "Greater Noida" → matches "Noida"
        ).values_list('user_id', flat=True)
        other_vendors = other_vendors.filter(user_id__in=city_user_ids)

    if not other_vendors.exists():
        return {}

    competitor_items = FoodItem.objects.filter(
        vendor__in=other_vendors,
        is_available=True,
    ).values('food_title', 'price')

    price_map = {}
    for item in competitor_items:
        key = item['food_title'].lower().strip()
        price_map.setdefault(key, []).append(float(item['price']))

    return {
        key: {
            'min':   min(prices),
            'max':   max(prices),
            'avg':   round(sum(prices) / len(prices), 2),
            'count': len(prices),
        }
        for key, prices in price_map.items()
    }


def find_similar_competitor(my_item_title, competitor_map):
    """
    Word-overlap matcher: finds the best matching competitor item title.
    Returns (matched_title, stats) or (None, None).
    """
    my_words   = set(my_item_title.lower().split())
    best_match = None
    best_score = 0

    for comp_title, stats in competitor_map.items():
        overlap = len(my_words & set(comp_title.split()))
        if overlap > best_score:
            best_score = overlap
            best_match = (comp_title, stats)

    if best_score >= 1 and best_match:
        return best_match
    return None, None


def build_price_comparison_data(vendor):
    """
    Main Phase 3 entry point.
    Returns a structured dict with per-item price status vs competitors.

    Shape:
    {
      'vendor_name': str,
      'city':        str,
      'items': [
        {
          'title', 'my_price', 'category',
          'competitor_min', 'competitor_max', 'competitor_avg',
          'competitor_count', 'matched_with',
          'status': 'competitive' | 'expensive' | 'cheap' | 'no_data'
        }, ...
      ]
    }
    """
    city          = get_vendor_city(vendor)
    my_items      = get_vendor_items(vendor)
    competitor_map = get_competitor_prices(vendor, city=city)

    result_items = []

    for item in my_items:
        my_price = float(item['price'])
        title    = item['food_title']
        category = item['category__category_name']

        comp_title, comp_stats = find_similar_competitor(title, competitor_map)

        if comp_stats:
            avg = comp_stats['avg']
            if my_price > avg * 1.15:
                status = 'expensive'
            elif my_price < avg * 0.85:
                status = 'cheap'
            else:
                status = 'competitive'

            result_items.append({
                'title':            title,
                'my_price':         my_price,
                'category':         category,
                'competitor_min':   comp_stats['min'],
                'competitor_max':   comp_stats['max'],
                'competitor_avg':   avg,
                'competitor_count': comp_stats['count'],
                'matched_with':     comp_title,
                'status':           status,
            })
        else:
            result_items.append({
                'title':            title,
                'my_price':         my_price,
                'category':         category,
                'competitor_min':   None,
                'competitor_max':   None,
                'competitor_avg':   None,
                'competitor_count': 0,
                'matched_with':     None,
                'status':           'no_data',
            })

    return {
        'vendor_name': vendor.vendor_name,
        'city':        city or 'Unknown',
        'items':       result_items,
    }


def format_comparison_for_ai(comparison_data):
    """
    Serialise comparison data as plain text so the AI can write a short summary.
    """
    lines = [
        f"Vendor: {comparison_data['vendor_name']}",
        f"City: {comparison_data['city']}",
        "",
        "Menu Price Comparison:",
    ]
    for item in comparison_data['items']:
        line = f"- {item['title']} (₹{item['my_price']})"
        if item['competitor_avg']:
            line += (
                f" | Market avg: ₹{item['competitor_avg']}"
                f" (min ₹{item['competitor_min']}, max ₹{item['competitor_max']})"
                f" from {item['competitor_count']} competitor(s)"
                f" | Status: {item['status']}"
            )
        else:
            line += " | No competitor data found"
        lines.append(line)

    return "\n".join(lines)