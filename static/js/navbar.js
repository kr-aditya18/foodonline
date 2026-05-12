document.addEventListener('DOMContentLoaded', function () {

  /* ── Hamburger toggle ── */
  var hamburger = document.getElementById('nav-hamburger');
  var drawer    = document.getElementById('mobile-drawer');
  var icon      = document.getElementById('hamburger-icon');

  if (hamburger && drawer) {
    hamburger.addEventListener('click', function () {
      var open = drawer.classList.toggle('open');
      icon.className = open ? 'ti ti-x' : 'ti ti-menu-2';
      hamburger.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    });
  }

  /* ── Sync desktop <-> mobile location inputs ── */
  var desk   = document.getElementById('nav-location-input');
  var mobile = document.getElementById('nav-location-input-mobile');

  function syncInputs(src, tgt) {
    if (src && tgt) {
      src.addEventListener('input', function () {
        tgt.value = src.value;
      });
    }
  }
  syncInputs(desk, mobile);
  syncInputs(mobile, desk);

  /* ── Mobile detect button fires desktop detect button ── */
  var mobileDetect  = document.getElementById('nav-detect-btn-mobile');
  var desktopDetect = document.getElementById('nav-detect-btn');

  if (mobileDetect && desktopDetect) {
    mobileDetect.addEventListener('click', function () {
      desktopDetect.click();
    });
  }

});