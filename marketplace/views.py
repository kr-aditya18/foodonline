import json
import math
from django.shortcuts import render, get_object_or_404
from vendor.models import Vendor
from menu.models import Category, FoodItem
from django.db.models import Q, Prefetch
from django.http import JsonResponse
from .models import Cart
from .context_processors import get_cart_counter, get_cart_amounts
from django.contrib.auth.decorators import login_required


# ─── HAVERSINE DISTANCE ─────────────────────────────────────────────────────
def _haversine_km(lat1, lon1, lat2, lon2):
    """Return great-circle distance in km between two (lat, lon) points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def marketplace(request):
    vendors = Vendor.objects.filter(is_approved=True, user__is_active=True)
    return render(request, 'marketplace/listings.html', {
        'vendors': vendors,
        'vendor_count': vendors.count(),
    })


def vendor_detail(request, vendor_slug):
    vendor = get_object_or_404(Vendor, vendor_slug=vendor_slug)

    categories = Category.objects.filter(vendor=vendor).prefetch_related(
        Prefetch(
            'fooditems',
            queryset=FoodItem.objects.filter(is_available=True)
        )
    )

    cart_quantities = {}
    if request.user.is_authenticated:
        cart_items = Cart.objects.filter(user=request.user).select_related('fooditems')
        cart_quantities = {item.fooditems.id: item.quantity for item in cart_items}

    return render(request, 'marketplace/vendor_detail.html', {
        'vendor': vendor,
        'categories': categories,
        'cart_quantities_json': json.dumps(cart_quantities),
    })


# ─── ADD TO CART ────────────────────────────────────────────────────────────
def add_to_cart(request, food_id):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'login_required', 'message': 'Please login to continue'})

    if request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return JsonResponse({'status': 'failed', 'message': 'Invalid request'})

    fooditem = get_object_or_404(FoodItem, id=food_id)

    cart_item, created = Cart.objects.get_or_create(
        user=request.user,
        fooditems=fooditem,
        defaults={'quantity': 1}
    )

    if not created:
        cart_item.quantity += 1
        cart_item.save()

    return JsonResponse({
        'status': 'success',
        'message': 'Cart updated',
        'cart_counter': get_cart_counter(request),
        'qty': cart_item.quantity,
        'cart_amount': get_cart_amounts(request),
    })


# ─── DECREASE CART ──────────────────────────────────────────────────────────
def decrease_cart(request, food_id):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'login_required', 'message': 'Please login to continue'})

    if request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return JsonResponse({'status': 'failed', 'message': 'Invalid request'})

    fooditem = get_object_or_404(FoodItem, id=food_id)

    try:
        cart_item = Cart.objects.get(user=request.user, fooditems=fooditem)

        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
            qty = cart_item.quantity
        else:
            cart_item.delete()
            qty = 0

        return JsonResponse({
            'status': 'success',
            'message': 'Cart updated',
            'cart_counter': get_cart_counter(request),
            'qty': qty,
            'cart_amount': get_cart_amounts(request),
        })

    except Cart.DoesNotExist:
        return JsonResponse({'status': 'failed', 'message': 'Item not found'})


# ─── DELETE CART ────────────────────────────────────────────────────────────
def delete_cart(request, cart_id):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'login_required', 'message': 'Please login to continue'})

    if request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return JsonResponse({'status': 'failed', 'message': 'Invalid Request'})

    try:
        cart_item = Cart.objects.get(user=request.user, id=cart_id)
        cart_item.delete()
        return JsonResponse({
            'status': 'success',
            'message': 'Cart item removed',
            'cart_counter': get_cart_counter(request),
            'cart_amount': get_cart_amounts(request),
        })

    except Cart.DoesNotExist:
        return JsonResponse({'status': 'failed', 'message': 'Cart item not found'})


# ─── CART PAGE ──────────────────────────────────────────────────────────────
@login_required(login_url='login')
def cart(request):
    cart_items = (
        Cart.objects
        .filter(user=request.user)
        .select_related('fooditems__category__vendor')
        .order_by('created_at')
    )
    return render(request, 'marketplace/cart.html', {'cart_items': cart_items})


# ─── SEARCH ─────────────────────────────────────────────────────────────────
def search(request):
    keyword = request.GET.get('rest_name', '').strip()
    address = request.GET.get('address', '').strip()
    city    = request.GET.get('city', '').strip()
    radius  = request.GET.get('radius', '').strip()

    # Try to read lat/lng submitted by the autocomplete JS hidden fields
    try:
        search_lat = float(request.GET.get('lat', ''))
        search_lng = float(request.GET.get('lng', ''))
        has_coords = True
    except (ValueError, TypeError):
        has_coords = False

    # ── Base vendor queryset ─────────────────────────────────────────────────
    vendors = Vendor.objects.filter(
        is_approved=True, user__is_active=True
    ).select_related('user_profile')

    # Filter vendors by restaurant name keyword
    if keyword:
        vendors = vendors.filter(vendor_name__icontains=keyword)

    # ── Radius filtering (precise Haversine) ────────────────────────────────
    if has_coords and radius:
        try:
            radius_km = float(radius)
        except ValueError:
            radius_km = None

        if radius_km:
            in_range_ids = []
            for vendor in vendors:
                profile = vendor.user_profile
                try:
                    v_lat = float(profile.latitude)
                    v_lng = float(profile.longitude)
                except (ValueError, TypeError):
                    continue
                distance = _haversine_km(search_lat, search_lng, v_lat, v_lng)
                if distance <= radius_km:
                    in_range_ids.append(vendor.id)
            vendors = vendors.filter(id__in=in_range_ids)

    # ── City/text fallback ───────────────────────────────────────────────────
    elif city or address:
        location_query = city or address
        vendors = vendors.filter(
            Q(user_profile__city__icontains=location_query) |
            Q(user_profile__address__icontains=location_query) |
            Q(user_profile__state__icontains=location_query)
        )

    # ── Food item search ─────────────────────────────────────────────────────
    # Search FoodItems whose title or description matches the keyword.
    # Also merge the vendors who serve those food items into the restaurant results.
    food_items = []

    if keyword:
        food_items = FoodItem.objects.filter(
            Q(food_title__icontains=keyword) |
            Q(description__icontains=keyword),
            is_available=True,
            vendor__is_approved=True,
            vendor__user__is_active=True,
        ).select_related('vendor', 'vendor__user_profile', 'category')

        # Collect vendor IDs that have a matching food item
        vendor_ids_from_food = food_items.values_list('vendor_id', flat=True).distinct()

        # Merge into the restaurant results (union — no duplicates)
        all_vendor_ids = set(vendors.values_list('id', flat=True)) | set(vendor_ids_from_food)
        vendors = Vendor.objects.filter(
            id__in=all_vendor_ids
        ).select_related('user_profile')

    context = {
        'vendors'         : vendors,
        'keyword'         : keyword,
        'address'         : address,
        'radius'          : radius,
        'vendor_count'    : vendors.count(),
        'food_items'      : food_items,
        'food_item_count' : len(food_items),
    }
    return render(request, 'marketplace/search.html', context)