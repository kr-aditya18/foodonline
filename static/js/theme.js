// Theme Toggle — Dark / Light Mode
// Persists preference in localStorage

(function () {
    // Apply theme immediately on page load (before DOM renders) to avoid flash
    var saved = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
})();

$(document).ready(function () {

    var $btn = $('#theme-toggle');
    var $icon = $('#theme-icon');

    // Sync icon to current theme on load
    function syncIcon(theme) {
        if (theme === 'dark') {
            $icon.removeClass('icon-sun').addClass('icon-moon');
            $btn.attr('title', 'Switch to Light Mode');
        } else {
            $icon.removeClass('icon-moon').addClass('icon-sun');
            $btn.attr('title', 'Switch to Dark Mode');
        }
    }

    var current = localStorage.getItem('theme') || 'light';
    syncIcon(current);

    // Toggle on click
    $btn.on('click', function () {
        var next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
        syncIcon(next);
    });
});