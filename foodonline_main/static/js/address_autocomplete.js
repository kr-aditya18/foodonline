// Address Autocomplete using OpenStreetMap Nominatim API (FREE - No API key needed)

$(document).ready(function () {

    if ($('#id_address').length === 0) return;

    // Helper: extract a postcode-like string from display_name
    // e.g. "Some Street, City, 110001, India" → "110001"
    function extractPostcodeFromText(text) {
        // Match 4–10 digit numeric strings (covers most postal code formats worldwide)
        var match = text.match(/\b\d{4,10}\b/);
        return match ? match[0] : '';
    }

    // Helper: fill a field only if it's currently empty
    function fillIfEmpty(selector, value) {
        if (value && !$(selector).val()) {
            $(selector).val(value);
        }
    }

    $('#id_address').autocomplete({
        source: function (request, response) {
            $.ajax({
                url: 'https://nominatim.openstreetmap.org/search',
                data: {
                    q: request.term,
                    format: 'json',
                    addressdetails: 1,
                    limit: 5,
                },
                headers: { 'Accept-Language': 'en' },
                success: function (data) {
                    if (data.length === 0) {
                        response([{ label: 'No results found', value: '' }]);
                        return;
                    }
                    response($.map(data, function (item) {
                        return {
                            label: item.display_name,
                            value: item.display_name,
                            address: item.address,
                            lat: item.lat,
                            lon: item.lon,
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

            var addr    = ui.item.address;
            var lat     = ui.item.lat;
            var lon     = ui.item.lon;

            $('#id_address').val(ui.item.value);
            $('#id_latitude').val(lat);
            $('#id_longitude').val(lon);

            // --- City ---
            var city = addr.city || addr.town || addr.village || addr.suburb || addr.county || '';
            $('#id_city').val(city);

            // --- State ---
            $('#id_state').val(addr.state || addr.region || '');

            // --- Country ---
            $('#id_country').val(addr.country || '');

            // --- Pincode: try all known Nominatim keys first ---
            var pincode = addr.postcode
                || addr.postal_code
                || addr['addr:postcode']
                || '';

            // Fallback 1: extract from display_name string
            if (!pincode) {
                pincode = extractPostcodeFromText(ui.item.value);
            }

            $('#id_pincode').val(pincode);

            // Fallback 2: reverse geocode if still empty
            if (!pincode) {
                $.ajax({
                    url: 'https://nominatim.openstreetmap.org/reverse',
                    data: {
                        lat: lat,
                        lon: lon,
                        format: 'json',
                        addressdetails: 1,
                        zoom: 18,
                    },
                    headers: { 'Accept-Language': 'en' },
                    success: function (data) {
                        if (data && data.address) {
                            var r = data.address;
                            var found = r.postcode
                                || r.postal_code
                                || r['addr:postcode']
                                || extractPostcodeFromText(data.display_name || '')
                                || '';

                            if (found) $('#id_pincode').val(found);

                            // Backfill other empty fields from reverse result
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
        'z-index': '9999',
        'max-height': '250px',
        'overflow-y': 'auto',
        'font-size': '14px',
    });
});