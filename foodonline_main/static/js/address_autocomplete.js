// Address Autocomplete using OpenStreetMap Nominatim API (FREE - No API key needed)

$(document).ready(function () {

    // ─── HELPER FUNCTIONS ───────────────────────────────────────────────────────
    function extractPostcodeFromText(text) {
        var match = text.match(/\b\d{4,10}\b/);
        return match ? match[0] : '';
    }

    function fillIfEmpty(selector, value) {
        if (value && !$(selector).val()) {
            $(selector).val(value);
        }
    }


    // ─── 1. VENDOR PROFILE PAGE ─────────────────────────────────────────────────
    // Fills: address, lat, lng, city, state, country, pincode
    if ($('#id_address').length) {

        $('#id_address').autocomplete({
            source: function (request, response) {
                $.ajax({
                    url: 'https://nominatim.openstreetmap.org/search',
                    data: { q: request.term, format: 'json', addressdetails: 1, limit: 5 },
                    headers: { 'Accept-Language': 'en' },
                    success: function (data) {
                        if (data.length === 0) {
                            response([{ label: 'No results found', value: '' }]);
                            return;
                        }
                        response($.map(data, function (item) {
                            return {
                                label  : item.display_name,
                                value  : item.display_name,
                                address: item.address,
                                lat    : item.lat,
                                lon    : item.lon,
                            };
                        }));
                    },
                    error: function () {
                        response([{ label: 'Error fetching results', value: '' }]);
                    }
                });
            },
            minLength: 3,
            delay: 400,
            select: function (event, ui) {
                if (!ui.item.address) return;

                var addr = ui.item.address;
                var lat  = ui.item.lat;
                var lon  = ui.item.lon;

                $('#id_address').val(ui.item.value);
                $('#id_latitude').val(lat);
                $('#id_longitude').val(lon);

                var city = addr.city || addr.town || addr.village || addr.suburb || addr.county || '';
                $('#id_city').val(city);
                $('#id_state').val(addr.state || addr.region || '');
                $('#id_country').val(addr.country || '');

                var pincode = addr.postcode || addr.postal_code || addr['addr:postcode'] || '';
                if (!pincode) pincode = extractPostcodeFromText(ui.item.value);
                $('#id_pincode').val(pincode);

                // Fallback reverse geocode for pincode
                if (!pincode) {
                    $.ajax({
                        url: 'https://nominatim.openstreetmap.org/reverse',
                        data: { lat: lat, lon: lon, format: 'json', addressdetails: 1, zoom: 18 },
                        headers: { 'Accept-Language': 'en' },
                        success: function (data) {
                            if (data && data.address) {
                                var r = data.address;
                                var found = r.postcode || r.postal_code || r['addr:postcode']
                                    || extractPostcodeFromText(data.display_name || '') || '';
                                if (found) $('#id_pincode').val(found);
                                fillIfEmpty('#id_city',    r.city || r.town || r.village || r.suburb || r.county || '');
                                fillIfEmpty('#id_state',   r.state || r.region || '');
                                fillIfEmpty('#id_country', r.country || '');
                            }
                        }
                    });
                }
                return false;
            }
        });

        $('#id_address').autocomplete('widget').css({
            'z-index'   : '9999',
            'max-height': '250px',
            'overflow-y': 'auto',
            'font-size' : '14px',
        });
    }


    // ─── 2. HOME PAGE SEARCH ────────────────────────────────────────────────────
    // Fills: city (hidden), lat (hidden), lng (hidden)
    if ($('#id_search_location').length) {

        $('#id_search_location').autocomplete({
            source: function (request, response) {
                $.ajax({
                    url: 'https://nominatim.openstreetmap.org/search',
                    data: { q: request.term, format: 'json', addressdetails: 1, limit: 5 },
                    headers: { 'Accept-Language': 'en' },
                    success: function (data) {
                        if (data.length === 0) {
                            response([{ label: 'No results found', value: '' }]);
                            return;
                        }
                        response($.map(data, function (item) {
                            return {
                                label  : item.display_name,
                                value  : item.display_name,
                                address: item.address,
                                lat    : item.lat,
                                lon    : item.lon,
                            };
                        }));
                    },
                    error: function () {
                        response([{ label: 'Error fetching results', value: '' }]);
                    }
                });
            },
            minLength: 3,
            delay: 400,
            select: function (event, ui) {
                if (!ui.item.address) return;

                var addr = ui.item.address;

                // Show the full selected name in the visible input
                $('#id_search_location').val(ui.item.value);

                // City for text-based fallback filtering
                var city = addr.city || addr.town || addr.village || addr.suburb || addr.county || '';
                $('#id_search_city').val(city);

                // Lat/lng for radius-based filtering
                $('#id_search_lat').val(ui.item.lat || '');
                $('#id_search_lng').val(ui.item.lon || '');

                return false;
            }
        });

        $('#id_search_location').autocomplete('widget').css({
            'z-index'   : '9999',
            'max-height': '250px',
            'overflow-y': 'auto',
            'font-size' : '14px',
        });
    }

});