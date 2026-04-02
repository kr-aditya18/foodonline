from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.contrib.gis.geos import Point
from django.utils.safestring import mark_safe
from .models import User, UserProfile
from django.contrib.auth.admin import UserAdmin


# ── User ──────────────────────────────────────────────────────────────────────
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'username', 'is_active')
    ordering = ('-date_joined',)
    filter_horizontal = ()
    list_filter = ()
    fieldsets = ()

admin.site.register(User, CustomUserAdmin)


# ── UserProfile ───────────────────────────────────────────────────────────────
@admin.register(UserProfile)
class UserProfileAdmin(GISModelAdmin):
    list_display    = ('user', 'city', 'state', 'country')
    exclude         = ('location',)
    readonly_fields = ('location_map',)

    def location_map(self, obj):
        if not obj.latitude or not obj.longitude:
            return 'No coordinates set.'
        lat = obj.latitude
        lon = obj.longitude
        return mark_safe(f"""
            <div id="admin-map" style="width:700px;height:450px;border:1px solid #444;background:#000;"></div>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/ol@9.2.4/dist/ol.css"/>
            <script src="https://cdn.jsdelivr.net/npm/ol@9.2.4/dist/ol.js"></script>
            <script>
            (function() {{
                // Satellite tile source (Esri World Imagery)
                var satelliteSource = new ol.source.XYZ({{
                    url: 'https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
                    crossOrigin: 'anonymous',
                    maxZoom: 19,
                    attributions: 'Esri World Imagery'
                }});

                var map = new ol.Map({{
                    target: 'admin-map',
                    layers: [
                        new ol.layer.Tile({{ source: satelliteSource }})
                    ],
                    view: new ol.View({{
                        center: ol.proj.fromLonLat([{lon}, {lat}]),
                        zoom: 16,
                        minZoom: 2,
                        maxZoom: 19
                    }}),
                    interactions: new ol.Collection([]),  // no drag/pan
                    controls: ol.control.defaults.defaults({{ attribution: false }})
                }});

                // Red marker
                var marker = new ol.Feature({{
                    geometry: new ol.geom.Point(ol.proj.fromLonLat([{lon}, {lat}]))
                }});
                marker.setStyle(new ol.style.Style({{
                    image: new ol.style.Circle({{
                        radius: 10,
                        fill: new ol.style.Fill({{ color: '#e74c3c' }}),
                        stroke: new ol.style.Stroke({{ color: '#ffffff', width: 2.5 }})
                    }})
                }}));

                var vectorLayer = new ol.layer.Vector({{
                    source: new ol.source.Vector({{ features: [marker] }})
                }});
                map.addLayer(vectorLayer);

                // If tiles fail to load, fall back to CartoDB
                satelliteSource.on('tileloaderror', function() {{
                    map.getLayers().item(0).setSource(new ol.source.XYZ({{
                        url: 'https://a.basemaps.cartocdn.com/rastertiles/voyager/{{z}}/{{x}}/{{y}}.png',
                        maxZoom: 19
                    }}));
                }});
            }})();
            </script>
        """)
    location_map.short_description = 'Location Map'

    def save_model(self, request, obj, form, change):
        if obj.latitude and obj.longitude:
            try:
                obj.location = Point(float(obj.longitude), float(obj.latitude), srid=4326)
            except (ValueError, TypeError):
                obj.location = None
        super().save_model(request, obj, form, change)