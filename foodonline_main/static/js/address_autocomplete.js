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

    // Returns the most specific locality name from a Nominatim address object
    // Priority: neighbourhood > suburb > city_district > town > village > city > county
    function getBestLocality(addr) {
        return addr.neighbourhood
            || addr.suburb
            || addr.city_district
            || addr.town
            || addr.village
            || addr.city
            || addr.county
            || '';
    }


    // ─── 1. NAVBAR LOCATION SEARCH ──────────────────────────────────────────────
    if ($('#nav-location-input').length) {

        var $navInput       = $('#nav-location-input');
        var $navSuggestions = $('#nav-suggestions');
        var $navDetectBtn   = $('#nav-detect-btn');
        var navDebounce     = null;

        // Restore saved label
        var savedLabel = localStorage.getItem('nav_location_label');
        if (savedLabel) $navInput.val(savedLabel);

        function navSaveAndRedirect(label, lat, lng) {
            localStorage.setItem('nav_location_label', label);
            localStorage.setItem('nav_lat', lat);
            localStorage.setItem('nav_lng', lng);
            $navInput.val(label);
            $navSuggestions.hide().empty();
            window.location.href = '/?lat=' + lat + '&lng=' + lng;
        }

        function navFetchSuggestions(query) {
            if (query.length < 3) {
                $navSuggestions.hide().empty();
                return;
            }

            $.ajax({
                url: 'https://nominatim.openstreetmap.org/search',
                data: { q: query, format: 'json', addressdetails: 1, limit: 5 },
                headers: { 'Accept-Language': 'en' },
                success: function (results) {
                    $navSuggestions.empty();

                    if (!results.length) {
                        $navSuggestions.append(
                            $('<li>').text('No results found').css({
                                padding: '10px 14px', color: '#999', fontSize: '13px'
                            })
                        );
                        $navSuggestions.show();
                        return;
                    }

                    $.each(results, function (i, place) {
                        var locality = getBestLocality(place.address);

                        var $li = $('<li>').html(
                            '<span style="font-size:13px;font-weight:600;color:#222;display:block;">'
                            + (locality || place.display_name) + '</span>'
                            + '<span style="font-size:11px;color:#888;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                            + place.display_name + '</span>'
                        ).css({
                            padding: '9px 14px',
                            cursor: 'pointer',
                            borderBottom: '1px solid #f0f0f0',
                            background: '#fff'
                        });

                        $li.on('mouseenter', function () { $(this).css('background', '#fff8f8'); });
                        $li.on('mouseleave', function () { $(this).css('background', '#fff'); });
                        $li.on('mousedown', function (e) {
                            e.preventDefault();
                            navSaveAndRedirect(locality || place.display_name, place.lat, place.lon);
                        });

                        $navSuggestions.append($li);
                    });

                    $navSuggestions.show();
                },
                error: function () {
                    $navSuggestions.hide();
                }
            });
        }

        $navInput.on('input', function () {
            clearTimeout(navDebounce);
            var query = $(this).val().trim();
            navDebounce = setTimeout(function () {
                navFetchSuggestions(query);
            }, 400);
        });

        $navInput.on('blur', function () {
            setTimeout(function () { $navSuggestions.hide(); }, 200);
        });

        $navInput.on('focus', function () {
            if ($navSuggestions.children().length) $navSuggestions.show();
        });

        // GPS detect button - navbar
        $navDetectBtn.on('click', function () {
            if (!navigator.geolocation) {
                alert('Geolocation not supported');
                return;
            }
            $navDetectBtn.html('⏳');
            navigator.geolocation.getCurrentPosition(
                function (pos) {
                    var lat = pos.coords.latitude;
                    var lng = pos.coords.longitude;
                    $.ajax({
                        url: 'https://nominatim.openstreetmap.org/reverse',
                        // zoom:16 gives neighbourhood/suburb level detail
                        data: { lat: lat, lon: lng, format: 'json', addressdetails: 1, zoom: 16 },
                        headers: { 'Accept-Language': 'en' },
                        success: function (data) {
                            var label = (data.address && getBestLocality(data.address)) || 'My Location';
                            $navDetectBtn.html('<i class="icon-target5"></i>');
                            navSaveAndRedirect(label, lat, lng);
                        },
                        error: function () {
                            $navDetectBtn.html('<i class="icon-target5"></i>');
                            alert('Could not get your location.');
                        }
                    });
                },
                function () {
                    $navDetectBtn.html('<i class="icon-target5"></i>');
                    alert('Could not get your location.');
                }
            );
        });

        // Auto-redirect on home page if coords saved in localStorage
        var urlParams = new URLSearchParams(window.location.search);
        if (!urlParams.has('lat')) {
            var savedLat = localStorage.getItem('nav_lat');
            var savedLng = localStorage.getItem('nav_lng');
            if (savedLat && savedLng && window.location.pathname === '/') {
                window.location.href = '/?lat=' + savedLat + '&lng=' + savedLng;
            }
        }
    }


    // ─── 2. VENDOR PROFILE PAGE ─────────────────────────────────────────────────
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


    // ─── 3. HOME PAGE SEARCH ────────────────────────────────────────────────────
    if ($('#id_search_location').length) {

        $('#id_search_location').autocomplete({
            source: function (request, response) {
                $.ajax({
                    url: 'https://nominatim.openstreetmap.org/search',
                    data: { q: request.term, format: 'json', addressdetails: 1, limit: 6, countrycodes: 'in' },
                    headers: { 'Accept-Language': 'en' },
                    success: function (data) {
                        if (data.length === 0) {
                            response([{ label: 'No results found', value: '' }]);
                            return;
                        }
                        response($.map(data, function (item) {
                            var locality = getBestLocality(item.address);
                            return {
                                label  : item.display_name,
                                value  : locality || item.display_name,
                                city   : locality,
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
                $('#id_search_city').val(ui.item.city || '');
                $('#id_search_lat').val(ui.item.lat   || '');
                $('#id_search_lng').val(ui.item.lon   || '');
                $('#id_search_location').val(ui.item.value);
                return false;
            }
        });

        $('#id_search_location').autocomplete('widget').css({
            'z-index'   : '9999',
            'max-height': '250px',
            'overflow-y': 'auto',
            'font-size' : '14px',
        });

        // GPS detect button - home search bar
        $(document).on('click', '#home-detect-btn', function () {
            if (!navigator.geolocation) {
                alert('Geolocation is not supported by your browser.');
                return;
            }
            var $btn = $(this);
            $btn.html('⏳');
            navigator.geolocation.getCurrentPosition(
                function (pos) {
                    var lat = pos.coords.latitude;
                    var lng = pos.coords.longitude;
                    $.ajax({
                        url: 'https://nominatim.openstreetmap.org/reverse',
                        // zoom:16 = neighbourhood/suburb level, much more specific than city
                        data: { lat: lat, lon: lng, format: 'json', addressdetails: 1, zoom: 16 },
                        headers: { 'Accept-Language': 'en' },
                        success: function (data) {
                            var locality = (data.address && getBestLocality(data.address)) || '';
                            $('#id_search_location').val(locality || (data && data.display_name) || '');
                            $('#id_search_city').val(locality);
                            $('#id_search_lat').val(lat);
                            $('#id_search_lng').val(lng);
                            $btn.html('<i class="icon-target5"></i>');
                        },
                        error: function () {
                            $btn.html('<i class="icon-target5"></i>');
                            alert('Could not reverse geocode your location.');
                        }
                    });
                },
                function () {
                    $btn.html('<i class="icon-target5"></i>');
                    alert('Could not get your location. Please allow location access.');
                }
            );
        });
    }

});