from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from accounts.forms import UserProfileForm, UserInfoForm
from accounts.models import UserProfile
from orders.models import Order, OrderedFood
from ai_assistant.models import FoodReview 

@login_required(login_url='login')
def cprofile(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    if request.method == 'POST':
        profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)
        user_form = UserInfoForm(request.POST, instance=request.user)
        if profile_form.is_valid and user_form.is_valid():
            profile_form.save()
            user_form.save()
            messages.success(request, 'Profile Updated')
            return redirect('cprofile')
        else:
            print(profile_form.errors)
            print(user_form.errors)
    else:
        profile_form = UserProfileForm(instance=profile)
        user_form = UserInfoForm(instance=request.user)

    context = {
        'profile_form': profile_form,
        'user_form':    user_form,
        'profile':      profile,
    }
    return render(request, 'customers/cprofile.html', context)


@login_required(login_url='login')
def my_orders(request):
    orders = Order.objects.filter(
        user=request.user, is_ordered=True
    ).order_by('-created_at')
    context = {'orders': orders}
    return render(request, 'customers/my_orders.html', context)

@login_required(login_url='login')
def order_detail(request, order_number):
    order = get_object_or_404(Order, order_number=order_number,
                              user=request.user, is_ordered=True)
    ordered_food = OrderedFood.objects.filter(order=order)
    subtotal = sum(item.amount for item in ordered_food)

    # Phase 9 — reviewed item IDs
    reviewed_item_ids = set(
        FoodReview.objects.filter(
            customer=request.user,
            order=order
        ).values_list('order_item_id', flat=True)
    )

    context = {
        'order':               order,
        'ordered_food':        ordered_food,
        'subtotal':            subtotal,
        'reviewed_item_ids':   reviewed_item_ids,   # ← ADD THIS
    }
    return render(request, 'orders/order_detail.html', context)