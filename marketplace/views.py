import json
from django.shortcuts import render, get_object_or_404
from vendor.models import Vendor
from menu.models import Category, FoodItem
from django.db.models import Prefetch
from django.http import JsonResponse
from .models import Cart
from .context_processors import get_cart_counter,get_cart_amounts
from django.contrib.auth.decorators import login_required

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

    # Build {food_id: quantity} dict, then serialize to JSON for the template
    cart_quantities = {}
    if request.user.is_authenticated:
        cart_items = Cart.objects.filter(user=request.user).select_related('fooditems')
        cart_quantities = {item.fooditems.id: item.quantity for item in cart_items}

    return render(request, 'marketplace/vendor_detail.html', {
        'vendor': vendor,
        'categories': categories,
        'cart_quantities_json': json.dumps(cart_quantities),  # safe to embed in <script>
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
        'cart_amount': get_cart_amounts(request),   # fixed: actual call + correct spelling
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
            'cart_amount': get_cart_amounts(request),   # added
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
            'cart_amount': get_cart_amounts(request),   # added
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
    context = {
        'cart_items': cart_items,
    }
    return render(request, 'marketplace/cart.html', context)