/**
 * page-loader.js — FoodOnline
 * Shows on every page load for MIN_MS seconds. Simple.
 */
(function () {
  'use strict';

  var MESSAGES = [
    'Heating up the kitchen\u2026',
    'Plating your experience\u2026',
    'Checking today\u2019s specials\u2026',
    'Stirring things up\u2026',
    'Almost ready to serve\u2026',
    'Chopping fresh ingredients\u2026',
    'Just a moment, chef is busy\u2026',
  ];

  var MIN_MS   = 800;
  var msgTimer = null;
  var msgIdx   = 0;

  function buildLoader() {
    var el = document.createElement('div');
    el.id  = 'page-loader';
    el.innerHTML = [
      '<div class="pl-bar-track"><div class="pl-bar-bounce"></div></div>',
      '<div class="pl-brand">',
      '  <div class="pl-brand-logo">\uD83C\uDF7D\uFE0F</div>',
      '  <div class="pl-brand-name">Food<span>Online</span></div>',
      '</div>',
      '<div class="pl-orbit-wrap">',
      '  <div class="pl-ring"></div>',
      '  <span class="pl-food">\uD83C\uDF55</span>',
      '  <span class="pl-food">\uD83C\uDF5C</span>',
      '  <span class="pl-food">\uD83C\uDF54</span>',
      '  <span class="pl-food">\uD83C\uDF2E</span>',
      '  <div class="pl-center"><div class="pl-plate">\uD83C\uDF7D\uFE0F</div></div>',
      '</div>',
      '<div class="pl-dots">',
      '  <div class="pl-dot"></div>',
      '  <div class="pl-dot"></div>',
      '  <div class="pl-dot"></div>',
      '</div>',
      '<div class="pl-message" id="pl-message">' + MESSAGES[0] + '</div>',
    ].join('');
    return el;
  }

  function startCycling() {
    clearInterval(msgTimer);
    msgIdx = 0;
    var el = document.getElementById('pl-message');
    if (el) el.textContent = MESSAGES[0];
    msgTimer = setInterval(function () {
      var el = document.getElementById('pl-message');
      if (!el) return;
      el.classList.add('fade');
      setTimeout(function () {
        msgIdx = (msgIdx + 1) % MESSAGES.length;
        el.textContent = MESSAGES[msgIdx];
        el.classList.remove('fade');
      }, 350);
    }, 2200);
  }

  function stopCycling() { clearInterval(msgTimer); }

  function init() {
    var loader = buildLoader();
    // Start VISIBLE on every page load
    document.body.insertBefore(loader, document.body.firstChild);
    startCycling();

    // Hide after MIN_MS no matter what
    setTimeout(function () {
      stopCycling();
      var el = document.getElementById('page-loader');
      if (el) el.classList.add('fade-out');
    }, MIN_MS);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();