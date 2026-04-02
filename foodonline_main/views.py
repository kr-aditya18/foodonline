from django.http import HttpResponse
from django.shortcuts import render
from vendor.models import Vendor
import math

def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def home(request):
    vendors = Vendor.objects.filter(
        is_approved=True, user__is_active=True
    ).select_related('user_profile')

    try:
        user_lat = float(request.GET.get('lat', ''))
        user_lng = float(request.GET.get('lng', ''))
        has_location = True
    except (ValueError, TypeError):
        user_lat = user_lng = None
        has_location = False

    if has_location:
        vendors_with_dist = []
        for v in vendors:
            try:
                v_lat = float(v.user_profile.latitude)
                v_lng = float(v.user_profile.longitude)
                if not v_lat or not v_lng:
                    continue
            except (ValueError, TypeError, AttributeError):
                continue
            dist = _haversine_km(user_lat, user_lng, v_lat, v_lng)
            v.distance_km = round(dist, 2)
            vendors_with_dist.append((v, dist))

        vendors_with_dist.sort(key=lambda x: x[1])
        vendors = [v for v, d in vendors_with_dist[:8]]
    else:
        vendors = vendors[:8]

    context = {
        'vendors': vendors,
        'has_location': has_location,
    }
    return render(request, 'home.html', context)