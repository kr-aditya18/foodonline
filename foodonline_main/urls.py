"""
URL configuration for foodonline_main project.

FIX APPLIED:
  Removed namespace='ai_assistant' from the ai/ include.
  The app_name = 'ai_assistant' inside ai_assistant/urls.py
  already registers the namespace. Declaring it in BOTH places
  causes Django to double-register and recurse infinitely when
  {% url 'ai_assistant:chat_api' %} is resolved during template
  rendering on every request.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from . import views
from django.conf import settings
from django.conf.urls.static import static
from marketplace import views as MarketplaceViews


def health_check(request):
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check),
    path('', views.home, name='home'),
    path('accounts/', include('accounts.urls')),
    path('vendor/', include('vendor.urls')),
    path('marketplace/', include('marketplace.urls')),

    # ── AI Assistant ──────────────────────────────────────────────────────────
    # DO NOT add namespace= here. app_name in ai_assistant/urls.py handles it.
    # Adding namespace= in both places = RecursionError on every page load.
    path('ai/', include('ai_assistant.urls')),

    path('cart/', MarketplaceViews.cart, name='cart'),
    path('search/', MarketplaceViews.search, name='search'),
    path('checkout/', MarketplaceViews.checkout, name='checkout'),
    path('orders/', include('orders.urls')),
    path('demo/checkout/', include('orders.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)