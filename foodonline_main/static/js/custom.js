$(document).ready(function () {

    // ─── TOAST ──────────────────────────────────────────────────────────────────
    let toastTimer;
    function showToast(type, title, sub) {
        const configs = {
            success:  { bg: '#e8f8f0', color: '#22c55e', emoji: '✅' },
            removed:  { bg: '#fff4e5', color: '#f97316', emoji: '🗑️' },
            decrease: { bg: '#fef9c3', color: '#eab308', emoji: '➖' },
            deleted:  { bg: '#fce7f3', color: '#ec4899', emoji: '🗑️' },
            error:    { bg: '#fee2e2', color: '#ef4444', emoji: '❌' },
        };
        const c = configs[type] || configs.error;

        $('#toast-icon-box').css('background', c.bg).html(`<span style="font-size:20px">${c.emoji}</span>`);
        $('#toast-title').text(title);
        $('#toast-sub').text(sub || '');
        $('#toast-bar').css({ background: c.color, animation: 'none' });
        setTimeout(() => $('#toast-bar').css('animation', 'shrink 2.2s linear forwards'), 10);

        clearTimeout(toastTimer);
        $('#food-toast').addClass('show');
        toastTimer = setTimeout(() => $('#food-toast').removeClass('show'), 2400);
    }

    // ─── MODAL ──────────────────────────────────────────────────────────────────
    function showModal(config) {
        $('#modal-banner').css('background', config.bannerBg);
        $('#modal-emoji').text(config.emoji);
        $('#modal-title').text(config.title);
        $('#modal-sub').text(config.sub);
        $('#modal-desc').text(config.desc);

        let html = '';
        if (config.primaryText)
            html += `<button class="btn-primary-modal" id="modal-primary-btn" style="background:${config.primaryColor}">${config.primaryText}</button>`;
        if (config.secondaryText)
            html += `<button class="btn-secondary-modal" id="modal-secondary-btn">${config.secondaryText}</button>`;
        $('#modal-actions').html(html);

        $('#food-overlay').addClass('show');
        setTimeout(() => $('#food-modal').addClass('show'), 10);

        $('#modal-primary-btn').off('click').on('click', () => { closeModal(); config.onPrimary?.(); });
        $('#modal-secondary-btn').off('click').on('click', closeModal);
        $('#food-overlay').off('click').on('click', (e) => { if ($(e.target).is('#food-overlay')) closeModal(); });
    }

    function closeModal() {
        $('#food-modal').removeClass('show');
        setTimeout(() => $('#food-overlay').removeClass('show'), 380);
    }

    // ─── MODAL PRESETS ──────────────────────────────────────────────────────────
    function handleLoginRequired() {
        showModal({
            bannerBg:     'linear-gradient(135deg, #ff6b35, #f7931e)',
            emoji:        '🍽️',
            title:        'Hungry? Login First!',
            sub:          'Your cart is waiting for you',
            desc:         'You need to be logged in to add items to your cart.',
            primaryText:  '🔑 Login Now',
            primaryColor: '#ff6b35',
            secondaryText:'Maybe Later',
            onPrimary: () => window.location.href = '/accounts/login/',
        });
    }

    function handleRestaurantClosed() {
        showModal({
            bannerBg:     'linear-gradient(135deg, #1e293b, #475569)',
            emoji:        '🔒',
            title:        'Restaurant is Closed',
            sub:          'We\'re not taking orders right now',
            desc:         'This restaurant is currently closed. Please check back during opening hours.',
            primaryText:  'Got it',
            primaryColor: '#475569',
        });
    }

    function handleError(msg) {
        showModal({
            bannerBg:     'linear-gradient(135deg, #ef4444, #f87171)',
            emoji:        '😕',
            title:        'Oops!',
            sub:          'Something went wrong',
            desc:         msg || 'An unexpected error occurred. Please try again.',
            primaryText:  'Got it',
            primaryColor: '#ef4444',
        });
    }

    function handleNetworkError() {
        showModal({
            bannerBg:     'linear-gradient(135deg, #6366f1, #818cf8)',
            emoji:        '📡',
            title:        'No Connection',
            sub:          'Could not reach the server',
            desc:         'Please check your internet connection and try again.',
            primaryText:  'Retry',
            primaryColor: '#6366f1',
            secondaryText:'Cancel',
        });
    }

    // ─── AJAX HELPER ────────────────────────────────────────────────────────────
    function cartAjax(url, onSuccess) {
        $.ajax({
            type: 'GET', url: url,
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            success: function (response) {
                if (response.status === 'login_required') { handleLoginRequired(); return; }
                if (response.status === 'restaurant_closed') { handleRestaurantClosed(); return; }
                if (response.status === 'failed') { handleError(response.message); return; }
                onSuccess(response);
            },
            error: handleNetworkError,
        });
    }

    // ─── UPDATE AMOUNTS ─────────────────────────────────────────────────────────
    function updateAmounts(cart_amount) {
        if (!cart_amount) return;

        $('#subtotal').text(cart_amount.subtotal);
        $('#grand_total').text(cart_amount.grand_total);

        if (cart_amount.tax_dict) {
            $.each(cart_amount.tax_dict, function (taxType, breakdown) {
                $.each(breakdown, function (percentage, amount) {
                    $('#tax-' + taxType).text(amount);
                });
            });
        }

        if (cart_amount.subtotal == 0) {
            $('[id^="tax-"]').text('0');
        }
    }

    // ─── CHECK EMPTY CART ───────────────────────────────────────────────────────
    function checkEmptyCart() {
        const remainingItems = $('#menu-item-list-6272 ul li').length;
        if (remainingItems === 0) {
            $('#menu-item-list-6272 ul').hide();
            $('#empty-cart').show();
            updateAmounts({ subtotal: 0, tax: 0, grand_total: 0, tax_dict: {} });
            $('[id^="tax-"]').text('0');
        }
    }

    // ─── ADD TO CART ────────────────────────────────────────────────────────────
    $('.add_to_cart').on('click', function (e) {
        e.preventDefault();
        const url     = $(this).data('url');
        const food_id = $(this).data('id');
        cartAjax(url, (response) => {
            $('#cart_counter').html(response.cart_counter.cart_count);
            $('#qty-' + food_id).text(response.qty);
            updateAmounts(response.cart_amount);
            showToast('success', 'Added to cart!', 'Item added successfully 🛒');
        });
    });

    // ─── DECREASE CART ──────────────────────────────────────────────────────────
    $('.decrease_cart').on('click', function (e) {
        e.preventDefault();
        const url     = $(this).data('url');
        const food_id = $(this).data('id');

        const $li        = $(this).closest('li');
        const liId       = $li.attr('id') || '';
        const isCartPage = liId.startsWith('cart-item-');
        const cart_id    = isCartPage ? liId.replace('cart-item-', '') : null;

        cartAjax(url, (response) => {
            $('#cart_counter').html(response.cart_counter.cart_count);
            updateAmounts(response.cart_amount);

            if (response.qty === 0 && isCartPage) {
                $('#cart-item-' + cart_id).fadeOut(300, function () {
                    $(this).remove();
                    showToast('removed', 'Item removed!', 'Removed from your cart 🗑️');
                    checkEmptyCart();
                });
            } else {
                $('#qty-' + food_id).text(response.qty);
                showToast(
                    response.qty === 0 ? 'removed'  : 'decrease',
                    response.qty === 0 ? 'Item removed!' : 'Quantity decreased',
                    response.qty === 0 ? 'Removed from your cart 🗑️' : `Now ${response.qty} in cart`
                );
            }
        });
    });

    // ─── DELETE CART ────────────────────────────────────────────────────────────
    $(document).on('click', '.delete_cart', function (e) {
        e.preventDefault();
        const url     = $(this).data('url');
        const cart_id = $(this).data('id');
        showModal({
            bannerBg:     'linear-gradient(135deg, #ef4444, #f87171)',
            emoji:        '🗑️',
            title:        'Remove Item?',
            sub:          'This will remove it from your cart',
            desc:         'Are you sure you want to completely remove this item?',
            primaryText:  'Yes, Remove',
            primaryColor: '#ef4444',
            secondaryText:'Cancel',
            onPrimary: () => cartAjax(url, (response) => {
                $('#cart-item-' + cart_id).fadeOut(300, function () {
                    $(this).remove();
                    $('#cart_counter').html(response.cart_counter.cart_count);
                    updateAmounts(response.cart_amount);
                    showToast('deleted', 'Item deleted!', 'Removed from your cart');
                    checkEmptyCart();
                });
            }),
        });
    });

});