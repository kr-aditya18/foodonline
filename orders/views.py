from django.http import JsonResponse
from django.shortcuts import render, redirect
from marketplace.views import Cart
from marketplace.context_processors import get_cart_amounts
from .forms import OrderForm
from .models import Order, Payment, OrderedFood
from menu.models import FoodItem
from decimal import Decimal
from .utils import generate_order_number
import requests
import razorpay
import hmac
import hashlib
import json
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.template.loader import render_to_string


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def make_serializable(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [make_serializable(i) for i in obj]
    return obj


def send_notification(mail_subject, mail_template, context):
    """Reusable HTML email sender."""
    message = render_to_string(mail_template, context)
    to_email = context.get('to_email')
    mail = EmailMessage(mail_subject, message, to=[to_email])
    mail.content_subtype = 'html'
    mail.send()


# ─────────────────────────────────────────────
# PayPal helpers
# ─────────────────────────────────────────────

def get_paypal_access_token():
    """
    Exchange PAYPAL_CLIENT_ID + PAYPAL_SECRET for a Bearer token.
    settings.py must have:
        PAYPAL_CLIENT_ID = config('PAYPAL_CLIENT_ID')
        PAYPAL_SECRET    = config('PAYPAL_SECRET')
        PAYPAL_MODE      = 'sandbox'   # or 'live'
    """
    client_id     = settings.PAYPAL_CLIENT_ID
    client_secret = settings.PAYPAL_SECRET
    mode          = getattr(settings, 'PAYPAL_MODE', 'sandbox')

    base_url = (
        "https://api-m.sandbox.paypal.com"
        if mode == 'sandbox'
        else "https://api-m.paypal.com"
    )

    response = requests.post(
        f"{base_url}/v1/oauth2/token",
        headers={
            "Accept":          "application/json",
            "Accept-Language": "en_US",
        },
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
    )
    data = response.json()
    if 'access_token' not in data:
        raise Exception(f"Could not get PayPal access token: {data}")
    return data['access_token']


def get_paypal_base_url():
    mode = getattr(settings, 'PAYPAL_MODE', 'sandbox')
    return (
        "https://api-m.sandbox.paypal.com"
        if mode == 'sandbox'
        else "https://api-m.paypal.com"
    )


# ─────────────────────────────────────────────
# Razorpay helper
# ─────────────────────────────────────────────

def get_razorpay_client():
    """
    Returns an authenticated Razorpay client.
    settings.py must have:
        RAZORPAY_KEY_ID     = config('RAZORPAY_KEY_ID')
        RAZORPAY_KEY_SECRET = config('RAZORPAY_KEY_SECRET')
    """
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


# ─────────────────────────────────────────────
# place_order  (billing form + review page)
# ─────────────────────────────────────────────

@login_required(login_url='login')
def place_order(request):
    cart_items = Cart.objects.filter(user=request.user).order_by('created_at')
    if cart_items.count() <= 0:
        return redirect('marketplace')

    # If user clicks "Edit Billing" — delete the pending order & restore form data
    if request.method == 'GET' and 'order_number' in request.session:
        try:
            old_order = Order.objects.get(
                order_number=request.session['order_number'],
                is_ordered=False
            )
            request.session['billing_data'] = {
                'first_name':     old_order.first_name,
                'last_name':      old_order.last_name,
                'phone':          old_order.phone,
                'email':          old_order.email,
                'address':        old_order.address,
                'country':        old_order.country,
                'city':           old_order.city,
                'pin_code':       old_order.pin_code,
                'payment_method': old_order.payment_method,
            }
            old_order.delete()
        except Order.DoesNotExist:
            pass
        del request.session['order_number']

    cart_amounts = get_cart_amounts(request)
    subtotal    = cart_amounts['subtotal']
    total_tax   = cart_amounts['tax']
    grand_total = cart_amounts['grand_total']
    tax_data    = cart_amounts['tax_dict']

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            order                = Order()
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
            order.payment_method = request.POST.get('payment_method', 'PayPal')
            order.save()
            order.order_number   = generate_order_number(order.id)
            order.save()

            request.session['order_number'] = order.order_number

            # Build cart_items list for template display
            cart_items_display = []
            for item in cart_items:
                cart_items_display.append({
                    'food_title': item.fooditems.food_title,
                    'price':      item.fooditems.price,
                    'quantity':   item.quantity,
                    'amount':     item.fooditems.price * item.quantity,
                })

            context = {
                'order':       order,
                'cart_items':  cart_items_display,
                'subtotal':    subtotal,
                'total_tax':   total_tax,
                'grand_total': grand_total,
                'tax_dict':    tax_data,
            }
            return render(request, 'orders/place_order.html', context)
        else:
            print(form.errors)

    billing_data = request.session.pop('billing_data', {})
    return render(request, 'orders/place_order.html', {
        'billing_data': billing_data,
        'subtotal':     subtotal,
        'grand_total':  grand_total,
        'tax_dict':     tax_data,
    })


# ─────────────────────────────────────────────
# PayPal — create order
# ─────────────────────────────────────────────

@csrf_exempt
def create_order(request):
    try:
        order_number = request.session.get('order_number')
        if not order_number:
            return JsonResponse({"error": "No order found in session"}, status=400)

        order        = Order.objects.get(order_number=order_number, user=request.user)
        access_token = get_paypal_access_token()
        base_url     = get_paypal_base_url()

        order_res = requests.post(
            f"{base_url}/v2/checkout/orders",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type":  "application/json",
            },
            json={
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {
                        "currency_code": "USD",
                        "value": str(round(order.total, 2))
                    }
                }]
            }
        )

        order_data = order_res.json()
        if 'id' not in order_data:
            return JsonResponse(
                {"error": "Failed to create PayPal order", "details": order_data},
                status=500
            )

        return JsonResponse({"id": order_data['id']})

    except Order.DoesNotExist:
        return JsonResponse({"error": "Order not found"}, status=404)
    except Exception as e:
        import traceback
        print("PAYPAL CREATE ERROR:", traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)


# ─────────────────────────────────────────────
# PayPal — capture order
# ─────────────────────────────────────────────

@csrf_exempt
def capture_order(request, order_id):
    try:
        access_token = get_paypal_access_token()
        base_url     = get_paypal_base_url()

        capture_res = requests.post(
            f"{base_url}/v2/checkout/orders/{order_id}/capture",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type":  "application/json",
            }
        )
        capture_data = capture_res.json()

        if capture_data.get('status') == 'COMPLETED':
            order_number = request.session.get('order_number')
            order        = Order.objects.get(order_number=order_number, user=request.user)
            transaction  = capture_data['purchase_units'][0]['payments']['captures'][0]

            payment = Payment.objects.create(
                user=request.user,
                transaction_id=transaction['id'],
                payment_method='PayPal',
                amount=transaction['amount']['value'],
                status=transaction['status'],
            )

            order.payment    = payment
            order.is_ordered = True
            order.status     = 'Accepted'
            order.save()

            cart_items   = Cart.objects.filter(user=request.user)
            vendors_seen = set()

            for item in cart_items:
                ordered_food          = OrderedFood()
                ordered_food.order    = order
                ordered_food.payment  = payment
                ordered_food.user     = request.user
                ordered_food.fooditem = item.fooditems
                ordered_food.quantity = item.quantity
                ordered_food.price    = item.fooditems.price
                ordered_food.amount   = item.fooditems.price * item.quantity
                ordered_food.save()
                vendors_seen.add(item.fooditems.vendor)

            # Email to customer
            ordered_food_to_customer = OrderedFood.objects.filter(order=order)
            send_notification(
                'Your Order Has Been Placed',
                'orders/emails/order_confirmation.html',
                {
                    'user':         request.user,
                    'order':        order,
                    'payment':      payment,
                    'ordered_food': ordered_food_to_customer,
                    'to_email':     order.email,
                }
            )

            # Email to each vendor
            for vendor in vendors_seen:
                vendor_food = OrderedFood.objects.filter(order=order, fooditem__vendor=vendor)
                send_notification(
                    'You Have Received a New Order',
                    'orders/emails/order_received_vendor.html',
                    {
                        'order':        order,
                        'payment':      payment,
                        'ordered_food': vendor_food,
                        'vendor':       vendor,
                        'to_email':     vendor.user.email,
                    }
                )

            cart_items.delete()
            del request.session['order_number']

            capture_data['order_number'] = order.order_number
            capture_data['payment_id']   = payment.transaction_id

        return JsonResponse(capture_data)

    except Exception as e:
        import traceback
        print("PAYPAL CAPTURE ERROR:", traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)


# ─────────────────────────────────────────────
# Razorpay — create order
# ─────────────────────────────────────────────

@csrf_exempt
def razorpay_create_order(request):
    """
    Called by the frontend to create a Razorpay order.
    Returns: razorpay_key, razorpay_order_id, amount (paise), currency
    """
    try:
        order_number = request.session.get('order_number')
        if not order_number:
            return JsonResponse({"error": "No order found in session"}, status=400)

        order  = Order.objects.get(order_number=order_number, user=request.user)
        client = get_razorpay_client()

        # Razorpay expects amount in paise (1 INR = 100 paise)
        amount_paise = int(order.total * 100)

        rzp_order = client.order.create({
            "amount":   amount_paise,
            "currency": "INR",
            "receipt":  order.order_number,
            "payment_capture": 1,   # auto-capture
        })

        return JsonResponse({
            "razorpay_key":      settings.RAZORPAY_KEY_ID,
            "razorpay_order_id": rzp_order['id'],
            "amount":            amount_paise,
            "currency":          "INR",
        })

    except Order.DoesNotExist:
        return JsonResponse({"error": "Order not found"}, status=404)
    except Exception as e:
        import traceback
        print("RAZORPAY CREATE ERROR:", traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)


# ─────────────────────────────────────────────
# Razorpay — capture / verify payment
# ─────────────────────────────────────────────

@csrf_exempt
def razorpay_capture_order(request):
    """
    Verifies Razorpay signature, marks order complete, sends emails.
    Expects JSON body:
        razorpay_payment_id, razorpay_order_id, razorpay_signature
    """
    try:
        data = json.loads(request.body)

        razorpay_payment_id = data.get('razorpay_payment_id', '')
        razorpay_order_id   = data.get('razorpay_order_id', '')
        razorpay_signature  = data.get('razorpay_signature', '')

        # ── Signature verification ──────────────────────────────────────────
        key_secret = settings.RAZORPAY_KEY_SECRET.encode('utf-8')
        message    = f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8')
        generated  = hmac.new(key_secret, message, hashlib.sha256).hexdigest()

        if generated != razorpay_signature:
            return JsonResponse({"error": "Invalid payment signature. Possible fraud."}, status=400)
        # ────────────────────────────────────────────────────────────────────

        order_number = request.session.get('order_number')
        order        = Order.objects.get(order_number=order_number, user=request.user)

        # Fetch payment details from Razorpay to get the actual amount captured
        client      = get_razorpay_client()
        rzp_payment = client.payment.fetch(razorpay_payment_id)
        amount_inr  = rzp_payment['amount'] / 100   # convert paise → INR

        payment = Payment.objects.create(
            user=request.user,
            transaction_id=razorpay_payment_id,
            payment_method='RazorPay',
            amount=amount_inr,
            status='COMPLETED',
        )

        order.payment    = payment
        order.is_ordered = True
        order.status     = 'Accepted'
        order.save()

        cart_items   = Cart.objects.filter(user=request.user)
        vendors_seen = set()

        for item in cart_items:
            ordered_food          = OrderedFood()
            ordered_food.order    = order
            ordered_food.payment  = payment
            ordered_food.user     = request.user
            ordered_food.fooditem = item.fooditems
            ordered_food.quantity = item.quantity
            ordered_food.price    = item.fooditems.price
            ordered_food.amount   = item.fooditems.price * item.quantity
            ordered_food.save()
            vendors_seen.add(item.fooditems.vendor)

        # Email to customer
        ordered_food_to_customer = OrderedFood.objects.filter(order=order)
        send_notification(
            'Your Order Has Been Placed',
            'orders/emails/order_confirmation.html',
            {
                'user':         request.user,
                'order':        order,
                'payment':      payment,
                'ordered_food': ordered_food_to_customer,
                'to_email':     order.email,
            }
        )

        # Email to each vendor
        for vendor in vendors_seen:
            vendor_food = OrderedFood.objects.filter(order=order, fooditem__vendor=vendor)
            send_notification(
                'You Have Received a New Order',
                'orders/emails/order_received_vendor.html',
                {
                    'order':        order,
                    'payment':      payment,
                    'ordered_food': vendor_food,
                    'vendor':       vendor,
                    'to_email':     vendor.user.email,
                }
            )

        cart_items.delete()
        del request.session['order_number']

        return JsonResponse({
            "order_number": order.order_number,
            "payment_id":   payment.transaction_id,
        })

    except Order.DoesNotExist:
        return JsonResponse({"error": "Order not found"}, status=404)
    except Exception as e:
        import traceback
        print("RAZORPAY CAPTURE ERROR:", traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)


# ─────────────────────────────────────────────
# Order complete page
# ─────────────────────────────────────────────

@login_required(login_url='login')
def order_complete(request):
    order_number = request.GET.get('order_number')
    payment_id   = request.GET.get('payment_id')

    try:
        order        = Order.objects.get(order_number=order_number, is_ordered=True)
        payment      = Payment.objects.get(transaction_id=payment_id)
        ordered_food = OrderedFood.objects.filter(order=order)
        subtotal     = sum(item.amount for item in ordered_food)

        context = {
            'order':        order,
            'payment':      payment,
            'ordered_food': ordered_food,
            'subtotal':     subtotal,
        }
        return render(request, 'orders/order_complete.html', context)
    except Exception:
        return redirect('home')