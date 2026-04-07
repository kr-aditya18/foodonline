from django.shortcuts import render, redirect
from marketplace.views import Cart
from marketplace.context_processors import get_cart_amounts
from .forms import OrderForm
from .models import Order
from decimal import Decimal
from .utils import generate_order_number

def make_serializable(obj):
    """Recursively convert Decimal values to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [make_serializable(i) for i in obj]
    return obj


def place_order(request):
    cart_items = Cart.objects.filter(user=request.user).order_by('created_at')
    if cart_items.count() <= 0:
        return redirect('marketplace')

    cart_amounts = get_cart_amounts(request)  # call once, not 4 times
    subtotal    = cart_amounts['subtotal']
    total_tax   = cart_amounts['tax']
    grand_total = cart_amounts['grand_total']
    tax_data    = cart_amounts['tax_dict']

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            order = Order()
            order.first_name     = form.cleaned_data['first_name']
            order.last_name      = form.cleaned_data['last_name']
            order.phone          = form.cleaned_data['phone']
            order.email          = form.cleaned_data['email']
            order.address        = form.cleaned_data['address']
            order.country        = form.cleaned_data['country']
            order.city           = form.cleaned_data['city']
            order.pin_code       = form.cleaned_data['pin_code']
            order.user           = request.user
            order.total          = float(grand_total)             
            order.tax_data       = make_serializable(tax_data)    
            order.total_tax      = float(total_tax)               
            order.payment_method = request.POST['payment_method']
            order.save() # order id or pk generated
            order.order_number   = generate_order_number(order.id)
            order.save()
            return redirect('place_order')
        else:
            print(form.errors)

    return render(request, 'orders/place_order.html')