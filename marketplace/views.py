import json
import math
from django.shortcuts import render, get_object_or_404,redirect
from accounts.models import UserProfile
from vendor.models import Vendor
from menu.models import Category, FoodItem
from django.db.models import Q, Prefetch
from django.http import JsonResponse
from .models import Cart
from .context_processors import get_cart_counter, get_cart_amounts
from django.contrib.auth.decorators import login_required
from vendor.utils import is_open_now, get_vendor_hours_context
from orders.forms import OrderForm
from marketplace.context_processors import get_cart_amounts
# ─── HAVERSINE DISTANCE ─────────────────────────────────────────────────────
def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ─── MARKETPLACE LISTING ────────────────────────────────────────────────────
def marketplace(request):
    vendors = Vendor.objects.filter(
        is_approved=True, user__is_active=True
    ).select_related('user_profile')

    vendor_list = [
        {'vendor': vendor, 'is_open': is_open_now(vendor)}
        for vendor in vendors
    ]

    return render(request, 'marketplace/listings.html', {
        'vendor_list' : vendor_list,
        'vendor_count': len(vendor_list),
    })


# ─── VENDOR DETAIL ──────────────────────────────────────────────────────────
def vendor_detail(request, vendor_slug):
    vendor = get_object_or_404(Vendor, vendor_slug=vendor_slug)

    categories = Category.objects.filter(vendor=vendor).prefetch_related(
        Prefetch('fooditems', queryset=FoodItem.objects.filter(is_available=True))
    )

    cart_quantities = {}
    if request.user.is_authenticated:
        cart_items = Cart.objects.filter(user=request.user).select_related('fooditems')
        cart_quantities = {item.fooditems.id: item.quantity for item in cart_items}

    hours_ctx = get_vendor_hours_context(vendor)

    return render(request, 'marketplace/vendor_detail.html', {
        'vendor'              : vendor,
        'categories'          : categories,
        'cart_quantities_json': json.dumps(cart_quantities),
        'today_slot'          : hours_ctx['today_slot'],
        'all_hours'           : hours_ctx['all_hours'],
        'is_open'             : hours_ctx['is_open'],
    })


# ─── ADD TO CART ────────────────────────────────────────────────────────────
def add_to_cart(request, food_id):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'login_required', 'message': 'Please login to continue'})
    if request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return JsonResponse({'status': 'failed', 'message': 'Invalid request'})

    fooditem = get_object_or_404(FoodItem, id=food_id)
    cart_item, created = Cart.objects.get_or_create(
        user=request.user, fooditems=fooditem, defaults={'quantity': 1}
    )
    if not created:
        cart_item.quantity += 1
        cart_item.save()

    return JsonResponse({
        'status': 'success', 'message': 'Cart updated',
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
            'status': 'success', 'message': 'Cart updated',
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
            'status': 'success', 'message': 'Cart item removed',
            'cart_counter': get_cart_counter(request),
            'cart_amount': get_cart_amounts(request),
        })
    except Cart.DoesNotExist:
        return JsonResponse({'status': 'failed', 'message': 'Cart item not found'})


# ─── CART PAGE ──────────────────────────────────────────────────────────────
@login_required(login_url='login')
def cart(request):
    cart_items = (
        Cart.objects.filter(user=request.user)
        .select_related('fooditems__category__vendor')
        .order_by('created_at')
    )
    return render(request, 'marketplace/cart.html', {'cart_items': cart_items})


# ─── SEARCH ─────────────────────────────────────────────────────────────────
def search(request):
    keyword = request.GET.get('rest_name', '').strip()
    address = request.GET.get('address', '').strip()
    radius  = request.GET.get('radius', '').strip()
    city    = request.GET.get('city', '').strip()

    try:
        search_lat = float(request.GET.get('lat', ''))
        search_lng = float(request.GET.get('lng', ''))
        has_coords = True
    except (ValueError, TypeError):
        has_coords = False

    vendors = Vendor.objects.filter(
        is_approved=True, user__is_active=True
    ).select_related('user_profile')

    food_items = []
    if keyword:
        food_items = FoodItem.objects.filter(
            Q(food_title__icontains=keyword) | Q(description__icontains=keyword),
            is_available=True, vendor__is_approved=True, vendor__user__is_active=True,
        ).select_related('vendor', 'vendor__user_profile', 'category')

        vendor_ids_by_name = set(vendors.filter(vendor_name__icontains=keyword).values_list('id', flat=True))
        vendor_ids_by_food = set(food_items.values_list('vendor_id', flat=True))
        vendors = Vendor.objects.filter(
            id__in=vendor_ids_by_name | vendor_ids_by_food,
            is_approved=True, user__is_active=True,
        ).select_related('user_profile')

    if has_coords:
        try:
            radius_km = float(radius) if radius else None
        except ValueError:
            radius_km = None

        vendors_with_distance = []
        for vendor in vendors:
            profile = vendor.user_profile
            try:
                v_lat = float(profile.latitude)
                v_lng = float(profile.longitude)
                if not v_lat or not v_lng:
                    continue
            except (ValueError, TypeError, AttributeError):
                continue
            distance = _haversine_km(search_lat, search_lng, v_lat, v_lng)
            if radius_km is None or distance <= radius_km:
                vendor.distance_km = round(distance, 2)
                vendors_with_distance.append((vendor, distance))

        vendors_with_distance.sort(key=lambda x: x[1])
        vendors = [v for v, d in vendors_with_distance]
        if food_items:
            vendor_ids_in_range = {v.id for v in vendors}
            food_items = [f for f in food_items if f.vendor_id in vendor_ids_in_range]

    elif city or address:
        location_query = city or address
        vendors = vendors.filter(
            Q(user_profile__city__icontains=location_query) |
            Q(user_profile__address__icontains=location_query) |
            Q(user_profile__state__icontains=location_query)
        )

    # Attach is_open to each vendor in search results
    vendor_list = [{'vendor': v, 'is_open': is_open_now(v)} for v in vendors]

    short_address = city or (address[:40] + '...' if len(address) > 40 else address)

    context = {
        'vendor_list'     : vendor_list,
        'keyword'         : keyword,
        'address'         : short_address,
        'radius'          : radius,
        'has_coords'      : has_coords,
        'vendor_count'    : len(vendor_list),
        'food_items'      : food_items,
        'food_item_count' : len(food_items) if isinstance(food_items, list) else food_items.count(),
    }
    return render(request, 'marketplace/search.html', context)

@login_required(login_url='login')
def checkout(request):
    cart_items = Cart.objects.filter(user=request.user).order_by('created_at')
    if cart_items.count() <= 0:
        return redirect('marketplace')
    
    user_profile = UserProfile.objects.get(user=request.user)
    default_values = {
        'first_name' : request.user.first_name,
        'last_name' : request.user.last_name,
        'phone' : request.user.phone_number,
        'email' : request.user.email,
        'address': user_profile.address,
        'country' : user_profile.country,
        'state' : user_profile.state,
        'city' : user_profile.city,
        'pin_code' : user_profile.pincode,
    }
    
    form = OrderForm(initial=default_values)
    cart_amounts = get_cart_amounts(request)  
    
    context = {
        'form': form,
        'cart_items': cart_items,
        'subtotal': cart_amounts['subtotal'],
        'tax_dict': cart_amounts['tax_dict'],
        'grand_total': cart_amounts['grand_total'],
    }
    return render(request, 'marketplace/checkout.html', context)