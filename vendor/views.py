from django.shortcuts import render, get_object_or_404, redirect
from .forms import VendorForm
from accounts.forms import UserProfileForm
from accounts.models import UserProfile
from .models import Vendor
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from accounts.views import check_role_vendor
from menu.models import Category, FoodItem
from menu.forms import CategoryForm, FoodItemForm
from django.utils.text import slugify
from django.http import JsonResponse
from django.db.models import Sum
from django.utils import timezone
import json
from .models import OpeningHour, DAYS, HOUR_OF_DAY_24
from orders.models import Order, OrderedFood


def get_vendor(request):
    vendor = Vendor.objects.get(user=request.user)
    return vendor


# ─────────────────────────────────────────────
# Lessons 204, 205, 208, 212, 213 — Vendor Dashboard
# ─────────────────────────────────────────────

@login_required(login_url='login')
@user_passes_test(check_role_vendor)
def vendordashboard(request):
    vendor = get_vendor(request)

    orders = Order.objects.filter(vendors=vendor, is_ordered=True).order_by('-created_at')
    recent_orders = orders[:10]

    # Lesson 212: Total revenue across all orders for this vendor
    total_revenue = OrderedFood.objects.filter(
        order__in=orders,
        fooditem__vendor=vendor,
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Lesson 213: Current month revenue
    now = timezone.now()
    current_month_revenue = OrderedFood.objects.filter(
        order__in=orders,
        fooditem__vendor=vendor,
        order__created_at__year=now.year,
        order__created_at__month=now.month,
    ).aggregate(total=Sum('amount'))['total'] or 0

    recent_orders_data = []
    for order in recent_orders:
        vendor_subtotal = OrderedFood.objects.filter(
            order=order,
            fooditem__vendor=vendor,
        ).aggregate(total=Sum('amount'))['total'] or 0
        recent_orders_data.append({
            'order':    order,
            'subtotal': vendor_subtotal,
        })

    context = {
        'total_orders':           orders.count(),
        'total_revenue':          total_revenue,
        'current_month_revenue':  current_month_revenue,
        'recent_orders_data':     recent_orders_data,
        'status_choices':         Order.STATUS,
    }
    return render(request, 'accounts/vendordashboard.html', context)


# ─────────────────────────────────────────────
# Lesson 207 — Vendor Order Detail
# ─────────────────────────────────────────────

@login_required(login_url='login')
@user_passes_test(check_role_vendor)
def vendor_order_detail(request, order_number):
    vendor = get_vendor(request)
    order = get_object_or_404(
        Order,
        order_number=order_number,
        vendors=vendor,
        is_ordered=True,
    )
    ordered_food = OrderedFood.objects.filter(order=order, fooditem__vendor=vendor)

    # Lesson 211: subtotal via middleware helper OR direct aggregate
    subtotal = ordered_food.aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'order':        order,
        'ordered_food': ordered_food,
        'subtotal':     subtotal,
        'vendor':       vendor,
    }
    return render(request, 'orders/vendor_order_detail.html', context)


# ─────────────────────────────────────────────
# Lesson 214 — Vendor My Orders (all orders)
# ─────────────────────────────────────────────

@login_required(login_url='login')
@user_passes_test(check_role_vendor)
def vendor_my_orders(request):
    vendor = get_vendor(request)
    orders = Order.objects.filter(vendors=vendor, is_ordered=True).order_by('-created_at')

    orders_data = []
    for order in orders:
        vendor_subtotal = OrderedFood.objects.filter(
            order=order,
            fooditem__vendor=vendor,
        ).aggregate(total=Sum('amount'))['total'] or 0
        orders_data.append({
            'order':    order,
            'subtotal': vendor_subtotal,
        })

    context = {'orders_data': orders_data}
    return render(request, 'vendor/vendor_orders.html', context)


# ─────────────────────────────────────────────
# Existing views — unchanged
# ─────────────────────────────────────────────

@login_required(login_url='login')
@user_passes_test(check_role_vendor)
def vprofile(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    vendor  = get_object_or_404(Vendor, user=request.user)

    if request.method == 'POST':
        profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)
        vendor_form  = VendorForm(request.POST, request.FILES, instance=vendor)
        if profile_form.is_valid() and vendor_form.is_valid():
            profile_form.save()
            vendor_form.save()
            messages.success(request, 'Settings updated.')
            return redirect('vprofile')
        else:
            print(profile_form.errors)
            print(vendor_form.errors)
    else:
        profile_form = UserProfileForm(instance=profile)
        vendor_form  = VendorForm(instance=vendor)

    context = {
        'profile_form': profile_form,
        'vendor_form':  vendor_form,
        'profile':      profile,
        'vendor':       vendor,
    }
    return render(request, 'vendor/vprofile.html', context)


@login_required(login_url='login')
@user_passes_test(check_role_vendor)
def menu_builder(request):
    vendor     = get_vendor(request)
    categories = Category.objects.filter(vendor=vendor).order_by('created_at')
    context    = {'categories': categories}
    return render(request, 'vendor/menu_builder.html', context)


@login_required(login_url='login')
@user_passes_test(check_role_vendor)
def fooditems_by_category(request, pk=None):
    vendor    = get_vendor(request)
    category  = get_object_or_404(Category, pk=pk)
    fooditems = FoodItem.objects.filter(vendor=vendor, category=category)
    context   = {'fooditems': fooditems, 'category': category}
    return render(request, 'vendor/fooditems_by_category.html', context)


@login_required(login_url='login')
@user_passes_test(check_role_vendor)
def add_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category        = form.save(commit=False)
            category.vendor = get_vendor(request)
            category.slug   = slugify(category.category_name)
            category.save()
            messages.success(request, 'Category added successfully.')
            return redirect('menu_builder')
    else:
        form = CategoryForm()
    return render(request, 'vendor/add_category.html', {'form': form})


@login_required(login_url='login')
@user_passes_test(check_role_vendor)
def edit_category(request, pk=None):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            category        = form.save(commit=False)
            category.vendor = get_vendor(request)
            category.slug   = slugify(category.category_name)
            category.save()
            messages.success(request, 'Category updated successfully.')
            return redirect('menu_builder')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'vendor/edit_category.html', {'form': form, 'category': category})


@login_required(login_url='login')
@user_passes_test(check_role_vendor)
def delete_category(request, pk=None):
    category = get_object_or_404(Category, pk=pk)
    category.delete()
    messages.success(request, 'Category deleted successfully.')
    return redirect('menu_builder')


@login_required(login_url='login')
@user_passes_test(check_role_vendor)
def add_food(request):
    if request.method == 'POST':
        form = FoodItemForm(request.POST, request.FILES)
        if form.is_valid():
            food        = form.save(commit=False)
            food.vendor = get_vendor(request)
            food.slug   = slugify(food.food_title)
            form.save()
            messages.success(request, 'Food item added successfully.')
            return redirect('fooditems_by_category', food.category.id)
    else:
        form = FoodItemForm()
        form.fields['category'].queryset = Category.objects.filter(vendor=get_vendor(request))
    return render(request, 'vendor/add_food.html', {'form': form})


@login_required(login_url='login')
@user_passes_test(check_role_vendor)
def edit_food(request, pk=None):
    food = get_object_or_404(FoodItem, pk=pk)
    if request.method == 'POST':
        form = FoodItemForm(request.POST, request.FILES, instance=food)
        if form.is_valid():
            foodtitle   = form.cleaned_data['food_title']
            food        = form.save(commit=False)
            food.vendor = get_vendor(request)
            food.slug   = slugify(foodtitle)
            form.save()
            messages.success(request, 'Food item updated successfully.')
            return redirect('fooditems_by_category', food.category.id)
    else:
        form = FoodItemForm(instance=food)
        form.fields['category'].queryset = Category.objects.filter(vendor=get_vendor(request))
    return render(request, 'vendor/edit_food.html', {'form': form, 'food': food})


@login_required(login_url='login')
@user_passes_test(check_role_vendor)
def delete_food(request, pk=None):
    food = get_object_or_404(FoodItem, pk=pk)
    food.delete()
    messages.success(request, 'Food item deleted successfully.')
    return redirect('fooditems_by_category', food.category.id)


@login_required(login_url='login')
@user_passes_test(check_role_vendor)
def opening_hours(request):
    vendor           = get_vendor(request)
    opening_hours_qs = OpeningHour.objects.filter(vendor=vendor).order_by('day', 'from_hour')
    context = {
        'opening_hours': opening_hours_qs,
        'days':          DAYS,
        'hours':         HOUR_OF_DAY_24,
    }
    return render(request, 'vendor/opening_hours.html', context)


@login_required(login_url='login')
@user_passes_test(check_role_vendor)
def add_opening_hour(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)

    day       = data.get('day')
    from_hour = data.get('from_hour')
    to_hour   = data.get('to_hour')
    is_closed = data.get('is_closed', False)

    if not day:
        return JsonResponse({'status': 'error', 'message': 'Please select a day.'}, status=400)

    vendor = get_vendor(request)
    if OpeningHour.objects.filter(vendor=vendor, day=day, is_closed=True).exists():
        return JsonResponse({'status': 'error', 'message': 'This day is already marked as closed.'}, status=400)

    if not is_closed:
        if not from_hour or not to_hour:
            return JsonResponse({'status': 'error', 'message': 'Provide both opening and closing times.'}, status=400)
        if from_hour >= to_hour:
            return JsonResponse({'status': 'error', 'message': 'Opening time must be before closing time.'}, status=400)
        for slot in OpeningHour.objects.filter(vendor=vendor, day=day, is_closed=False):
            if not (to_hour <= slot.from_hour or from_hour >= slot.to_hour):
                return JsonResponse({
                    'status':  'error',
                    'message': f'Overlaps with existing slot ({slot.from_hour}–{slot.to_hour}).'
                }, status=400)

    oh = OpeningHour.objects.create(
        vendor=vendor,
        day=day,
        from_hour=from_hour if not is_closed else '',
        to_hour=to_hour   if not is_closed else '',
        is_closed=is_closed,
    )
    return JsonResponse({
        'status':    'success',
        'id':        oh.id,
        'day':       oh.day,
        'from_hour': oh.from_hour,
        'to_hour':   oh.to_hour,
        'is_closed': oh.is_closed,
        'message':   'Opening hours added successfully.',
    })


@login_required(login_url='login')
@user_passes_test(check_role_vendor)
def delete_opening_hour(request, pk):
    if request.method != 'DELETE':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

    oh     = get_object_or_404(OpeningHour, pk=pk)
    vendor = get_vendor(request)
    if oh.vendor != vendor:
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)

    oh.delete()
    return JsonResponse({'status': 'success', 'message': 'Time slot removed.'})