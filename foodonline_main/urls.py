"""
URL configuration for foodonline_main project.
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

    path('cart/', MarketplaceViews.cart, name='cart'),

    # search
    path('search/', MarketplaceViews.search, name='search'),

    # checkout
    path('checkout/', MarketplaceViews.checkout, name='checkout'),

    # orders
    path('orders/', include('orders.urls')),
    path('demo/checkout/', include('orders.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)