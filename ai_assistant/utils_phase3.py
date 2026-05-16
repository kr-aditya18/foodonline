# ai_assistant/utils_phase3.py

from menu.models import FoodItem
from vendor.models import Vendor
from accounts.models import UserProfile
from django.db.models import Avg, Min, Max, Q


def get_vendor_city(vendor):
    """Get vendor's city from UserProfile."""
    try:
        profile = UserProfile.objects.get(user=vendor.user)
        return profile.city
    except UserProfile.DoesNotExist:
        return None


def get_vendor_items(vendor):
    """Get all food items for the current vendor."""
    items = FoodItem.objects.filter(
        vendor=vendor,
        is_available=True,
    ).select_related('category').values(
        'food_title', 'price', 'category__category_name'
    )
    return list(items)


def get_competitor_prices(vendor, city=None):
    """
    Get price data for similar items from other vendors.
    Filters by same city if available.
    Returns dict: {food_title_lower: {min, max, avg, count}}
    """
    # Get all other vendors
    other_vendors = Vendor.objects.filter(
        is_approved=True
    ).exclude(pk=vendor.pk)

    # Filter by city if available
    if city:
        # city comparison fuzzy 
        city_vendor_ids = UserProfile.objects.filter(
            city__icontains=city.split()[-1]  # "Greater Noida" → "Noida" se match
        ).values_list('user_id', flat=True)
        other_vendors = other_vendors.filter(user_id__in=city_vendor_ids)

    if not other_vendors.exists():
        return {}

    competitor_items = FoodItem.objects.filter(
        vendor__in=other_vendors,
        is_available=True,
    ).values('food_title', 'price')

    # Build price map: normalize title → prices
    price_map = {}
    for item in competitor_items:
        key = item['food_title'].lower().strip()
        if key not in price_map:
            price_map[key] = []
        price_map[key].append(float(item['price']))

    # Compute stats
    result = {}
    for key, prices in price_map.items():
        result[key] = {
            'min':   min(prices),
            'max':   max(prices),
            'avg':   round(sum(prices) / len(prices), 2),
            'count': len(prices),
        }
    return result


def find_similar_competitor(my_item_title, competitor_map):
    """
    Find best matching competitor item using simple word overlap.
    Returns (matched_title, stats) or (None, None).
    """
    my_words = set(my_item_title.lower().split())
    best_match = None
    best_score = 0

    for comp_title, stats in competitor_map.items():
        comp_words = set(comp_title.split())
        overlap = len(my_words & comp_words)
        if overlap > best_score:
            best_score = overlap
            best_match = (comp_title, stats)

    if best_score >= 1 and best_match:
        return best_match
    return None, None


def build_price_comparison_data(vendor):
    """
    Main function — returns structured comparison data.
    {
      'vendor_name': str,
      'city': str,
      'items': [
        {
          'title': str,
          'my_price': float,
          'category': str,
          'competitor_min': float|None,
          'competitor_max': float|None,
          'competitor_avg': float|None,
          'competitor_count': int,
          'status': 'competitive'|'expensive'|'cheap'|'no_data',
        }
      ]
    }
    """
    city = get_vendor_city(vendor)
    my_items = get_vendor_items(vendor)
    competitor_map = get_competitor_prices(vendor, city=city)

    result_items = []

    for item in my_items:
        my_price = float(item['price'])
        title    = item['food_title']
        category = item['category__category_name']

        comp_title, comp_stats = find_similar_competitor(title, competitor_map)

        if comp_stats:
            avg = comp_stats['avg']
            # Determine status
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
    Format comparison data as text for AI to summarize.
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