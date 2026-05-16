/**
 * FILE LOCATION:
 *   foodonline_main/static/ai_assistant/js/chatbot.js
 *
 * FoodOnline AI Assistant — Chat Widget Logic
 *
 * STRUCTURE DEPENDENCY:
 *   #foi-messages
 *     └── #foi-typing        ← typing indicator is a CHILD of #foi-messages
 *         └── .foi-bubble
 *   New message bubbles are inserted via insertBefore(wrapper, typingEl)
 *   so typing dots always stay at the very bottom.
 *
 * IMAGE GENERATION (tried in order, silent fallback on failure):
 *   1. Pollinations.ai  — AI food photo, unique seed every call
 *   2. Foodish API      — real food photos, keyword-matched, no key needed
 *   3. Canvas           — local JS render, zero network, NEVER fails
 *
 * IMAGE UPLOAD (Phase 4 addition):
 *   Vendor can manually upload their own photo if AI result doesn't match.
 *   Accepts image/*, max 5 MB, read as base64 DataURL and stored in
 *   card.dataset.imageUrl — same field saveFoodCard already reads,
 *   so NO backend changes are needed.
 */

(function () {
  'use strict';

  /* ══════════════════════════════════════════════════════════════
     IMAGE PROVIDERS
     Each function(title, desc, attempt) returns Promise<string>.
     `attempt` increments on every "Change Image" click so each
     provider can vary output without repeating the same image.
     Provider 3 (Canvas) ALWAYS resolves — it is the final net.
  ══════════════════════════════════════════════════════════════ */

  /* ── 1. Pollinations.ai ────────────────────────────────────────
     AI-generated food photo. Seed = timestamp + attempt + random
     so every call — including retries — is a genuinely fresh request
     that bypasses browser cache and Pollinations' own dedup logic.
  ─────────────────────────────────────────────────────────────── */
  function providerPollinations(title, desc, attempt) {
    return new Promise(function (resolve, reject) {
      var prompt = encodeURIComponent(
        'professional food photography of ' + title +
        (desc ? ', ' + desc.substring(0, 60) : '') +
        ', appetizing close-up, restaurant quality plating, ' +
        'soft natural light, shallow depth of field, clean background'
      );
      var seed = Date.now() + (attempt || 0) * 1337 + Math.floor(Math.random() * 99999);
      var url  = 'https://image.pollinations.ai/prompt/' + prompt +
                 '?width=400&height=300&nologo=true&model=flux&seed=' + seed;

      var img   = new Image();
      img.crossOrigin = 'anonymous';
      var timer = setTimeout(function () {
        img.onload = img.onerror = null;
        img.src = '';
        reject(new Error('Pollinations timeout'));
      }, 25000);

      img.onload  = function () { clearTimeout(timer); resolve(url); };
      img.onerror = function () { clearTimeout(timer); reject(new Error('Pollinations load error')); };
      img.src = url;
    });
  }

  /* ── 2. Foodish API ────────────────────────────────────────────
     Real food photos from foodish-api.com — free, no key, CORS-open.
     Maps dish keywords → API categories for relevance.
     Each call fetches a random image, so retries give fresh results.
  ─────────────────────────────────────────────────────────────── */
  function providerFoodish(title) {
    return new Promise(function (resolve, reject) {
      var MAP = [
        { words: ['biryani', 'rice', 'pulao', 'fried rice'], cat: 'rice'    },
        { words: ['pizza'],                                   cat: 'pizza'   },
        { words: ['burger', 'sandwich'],                      cat: 'burger'  },
        { words: ['pasta', 'noodle', 'spaghetti', 'penne'],  cat: 'pasta'   },
        { words: ['dosa', 'idli', 'uttapam', 'vada'],        cat: 'dosa'    },
        { words: ['roti', 'naan', 'paratha', 'chapati'],     cat: 'roti'    },
        { words: ['dessert', 'cake', 'sweet', 'halwa',
                  'kheer', 'gulab', 'ladoo'],                cat: 'dessert' },
      ];

      var lower = title.toLowerCase();
      var cat   = 'indian';
      for (var i = 0; i < MAP.length; i++) {
        if (MAP[i].words.some(function (w) { return lower.indexOf(w) !== -1; })) {
          cat = MAP[i].cat; break;
        }
      }

      fetch('https://foodish-api.com/api/images/' + cat)
        .then(function (r) {
          if (!r.ok) throw new Error('Foodish HTTP ' + r.status);
          return r.json();
        })
        .then(function (data) {
          if (!data || !data.image) throw new Error('Foodish: no image field');

          /* Verify the image actually loads before resolving */
          var img   = new Image();
          var timer = setTimeout(function () {
            img.onload = img.onerror = null;
            img.src = '';
            reject(new Error('Foodish image load timeout'));
          }, 12000);

          img.onload  = function () { clearTimeout(timer); resolve(data.image); };
          img.onerror = function () { clearTimeout(timer); reject(new Error('Foodish onerror')); };
          img.src = data.image;
        })
        .catch(function (err) { reject(err); });
    });
  }

  /* ── 3. Canvas — local, zero network, NEVER rejects ───────────
     Draws a styled gradient tile with food emoji + title text.
     `attempt` rotates the colour palette so "Change Image" gives
     a visually different result even for the same dish name.
  ─────────────────────────────────────────────────────────────── */
  function providerCanvas(title, attempt) {
    return new Promise(function (resolve) {
      var canvas = document.createElement('canvas');
      canvas.width  = 400;
      canvas.height = 300;
      var ctx = canvas.getContext('2d');

      var PALETTES = [
        ['#e65c00', '#f9d423'],
        ['#1a6b3c', '#a8e063'],
        ['#7b2ff7', '#f107a3'],
        ['#c94b4b', '#4b134f'],
        ['#005c97', '#363795'],
        ['#f7971e', '#ffd200'],
        ['#11998e', '#38ef7d'],
        ['#ee0979', '#ff6a00'],
      ];
      var idx  = ((title.charCodeAt(0) || 0) + (title.length) + (attempt || 0)) % PALETTES.length;
      var grad = ctx.createLinearGradient(0, 0, 400, 300);
      grad.addColorStop(0, PALETTES[idx][0]);
      grad.addColorStop(1, PALETTES[idx][1]);
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, 400, 300);

      /* Dot-grid texture */
      ctx.fillStyle = 'rgba(255,255,255,0.07)';
      for (var gx = 10; gx < 400; gx += 20) {
        for (var gy = 10; gy < 300; gy += 20) {
          ctx.beginPath();
          ctx.arc(gx, gy, 1.5, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      /* Radial vignette */
      var vig = ctx.createRadialGradient(200, 150, 50, 200, 150, 220);
      vig.addColorStop(0, 'rgba(0,0,0,0)');
      vig.addColorStop(1, 'rgba(0,0,0,0.4)');
      ctx.fillStyle = vig;
      ctx.fillRect(0, 0, 400, 300);

      /* Frosted circle */
      ctx.beginPath();
      ctx.arc(200, 118, 58, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,255,255,0.2)';
      ctx.fill();

      /* Keyword → emoji */
      var EMOJI_MAP = [
        { words: ['biryani', 'rice', 'pulao'],          e: '🍛' },
        { words: ['pizza'],                              e: '🍕' },
        { words: ['burger', 'sandwich'],                 e: '🍔' },
        { words: ['noodle', 'pasta', 'spaghetti'],       e: '🍜' },
        { words: ['dosa', 'idli', 'uttapam'],            e: '🥞' },
        { words: ['cake', 'dessert', 'halwa', 'sweet'],  e: '🍰' },
        { words: ['chicken', 'tikka', 'tandoor'],        e: '🍗' },
        { words: ['fish', 'prawn', 'seafood'],           e: '🐟' },
        { words: ['salad', 'bowl'],                      e: '🥗' },
        { words: ['roti', 'naan', 'paratha'],            e: '🫓' },
        { words: ['soup', 'dal', 'curry'],               e: '🍲' },
        { words: ['wrap', 'roll', 'kathi'],              e: '🌯' },
      ];
      var lower = title.toLowerCase();
      var emoji = '🍽️';
      for (var ei = 0; ei < EMOJI_MAP.length; ei++) {
        if (EMOJI_MAP[ei].words.some(function (w) { return lower.indexOf(w) !== -1; })) {
          emoji = EMOJI_MAP[ei].e; break;
        }
      }

      ctx.font = '58px serif';
      ctx.textAlign = 'center';
      ctx.fillText(emoji, 200, 142);

      /* Title — word-wrap */
      ctx.shadowColor = 'rgba(0,0,0,0.55)';
      ctx.shadowBlur  = 8;
      ctx.fillStyle   = '#ffffff';
      ctx.font        = 'bold 17px sans-serif';
      ctx.textAlign   = 'center';

      var words = title.split(' ');
      var lines = [];
      var line  = '';
      words.forEach(function (w) {
        var test = line ? line + ' ' + w : w;
        if (ctx.measureText(test).width > 340) { lines.push(line); line = w; }
        else line = test;
      });
      if (line) lines.push(line);

      var startY = 210;
      lines.forEach(function (l, li) { ctx.fillText(l, 200, startY + li * 22); });

      ctx.font      = '11px sans-serif';
      ctx.fillStyle = 'rgba(255,255,255,0.5)';
      ctx.shadowBlur = 0;
      ctx.fillText('preview — replace from dashboard', 200, startY + lines.length * 22 + 18);

      resolve(canvas.toDataURL('image/png'));
    });
  }

  /* ══════════════════════════════════════════════════════════════
     PROVIDER CHAIN RUNNER
     Tries providers 1 → 2 → 3 in sequence, stopping at first
     success. Logs failures to console (dev-visible, user-invisible).
  ══════════════════════════════════════════════════════════════ */
  function tryImageProviders(title, desc, attempt) {
    var PROVIDERS = [
      { name: 'Pollinations', fn: function () { return providerPollinations(title, desc, attempt); } },
      { name: 'Foodish',      fn: function () { return providerFoodish(title); } },
      { name: 'Canvas',       fn: function () { return providerCanvas(title, attempt); } },
    ];

    function tryNext(index) {
      if (index >= PROVIDERS.length) {
        return Promise.reject(new Error('All image providers exhausted'));
      }
      return PROVIDERS[index].fn().catch(function (err) {
        console.warn('[FoodOnline AI] Image provider "' + PROVIDERS[index].name + '" failed:', err.message);
        return tryNext(index + 1);
      });
    }

    return tryNext(0);
  }

  /* ══════════════════════════════════════════════════════════════
     CSRF HELPER
  ══════════════════════════════════════════════════════════════ */
  function getCookie(name) {
    var val = null;
    if (document.cookie) {
      document.cookie.split(';').forEach(function (c) {
        var t = c.trim();
        if (t.substring(0, name.length + 1) === name + '=') {
          val = decodeURIComponent(t.substring(name.length + 1));
        }
      });
    }
    if (!val && name === 'csrftoken') {
      var meta = document.querySelector('meta[name="csrf-token"]');
      if (meta) val = meta.getAttribute('content');
    }
    return val;
  }

  /* ══════════════════════════════════════════════════════════════
     CONFIG + STATE
  ══════════════════════════════════════════════════════════════ */
  var cfg = document.getElementById('foi-config');
  if (!cfg) return;

  var CHAT_API_URL    = cfg.dataset.chatUrl;
  var CLEAR_API_URL   = cfg.dataset.clearUrl;
  var HISTORY_API_URL = cfg.dataset.historyUrl;
  var STATUS_API_URL  = cfg.dataset.statusUrl;
  var IS_AUTH         = cfg.dataset.authenticated === 'true';
  var INITIAL_ROLE    = cfg.dataset.role || 'guest';

  var sessionKey     = localStorage.getItem('foi_session_key') || '';
  var isOpen         = false;
  var isTyping       = false;
  var currentRole    = INITIAL_ROLE;
  var recognition    = null;
  var isListening    = false;
  var preferredVoice = null;

  var fab          = document.getElementById('foi-fab');
  var fabDot       = document.getElementById('foi-fab-dot');
  var chatWin      = document.getElementById('foi-chat-window');
  var msgContainer = document.getElementById('foi-messages');
  var typingEl     = document.getElementById('foi-typing');
  var inputEl      = document.getElementById('foi-input');
  var sendBtn      = document.getElementById('foi-send-btn');
  var closeBtn     = document.getElementById('foi-close-btn');
  var clearBtn     = document.getElementById('foi-clear-btn');
  var roleLabel    = document.getElementById('foi-role-label');
  var suggsEl      = document.getElementById('foi-suggestions');
  var voiceBtn     = document.getElementById('foi-voice-btn');

  if (!fab || !chatWin || !msgContainer || !typingEl || !inputEl) {
    console.warn('FoodOnline AI: Required DOM elements missing.');
    return;
  }
  if (typingEl.parentElement !== msgContainer) {
    console.warn('FoodOnline AI: #foi-typing must be a direct child of #foi-messages.');
    return;
  }

  /* ══════════════════════════════════════════════════════════════
     ROLE CONFIG
  ══════════════════════════════════════════════════════════════ */
  var ROLE_CONFIG = {
    vendor: {
      label:   'Vendor',
      welcome: "👋 Hi! I'm your AI menu assistant. Describe any dish and I'll generate the perfect title, description, price, and tags. What would you like to add today?",
      chips:   ['Generate a food item 🍱', 'Compare my pricing 💰', 'Suggest categories 📋', 'Menu improvement tips ✨'],
    },
    customer: {
      label:   'Customer',
      welcome: "🍕 Hey there, foodie! Tell me what you're craving or how you're feeling and I'll find the perfect meal for you. What sounds good today?",
      chips:   ["I'm feeling spicy 🌶️", "Something healthy 🥗", "Restaurants near me 🗺️", "Track my orders 📦"],
    },
    guest: {
      label:   'Guest',
      welcome: "👋 Welcome to FoodOnline! I can help you discover restaurants and answer your questions. Log in for personalised recommendations!",
      chips:   ['How does FoodOnline work? 🤔', 'Find restaurants 🗺️', 'Register as a vendor 🏪', 'Login to my account 🔐'],
    },
  };

  /* ══════════════════════════════════════════════════════════════
     VOICE SETUP
  ══════════════════════════════════════════════════════════════ */
  function loadBestVoice() {
    if (!window.speechSynthesis) return;
    var voices = window.speechSynthesis.getVoices();
    if (!voices.length) return;
    var preferred = [
      'Google UK English Female', 'Google US English',
      'Microsoft Aria Online (Natural) - English (United States)',
      'Microsoft Jenny Online (Natural) - English (United States)',
      'Samantha', 'Karen', 'Daniel',
    ];
    for (var i = 0; i < preferred.length; i++) {
      var found = voices.find(function (v) { return v.name === preferred[i]; });
      if (found) { preferredVoice = found; return; }
    }
    preferredVoice =
      voices.find(function (v) { return v.lang.startsWith('en') && !v.localService; }) ||
      voices.find(function (v) { return v.lang.startsWith('en'); }) || null;
  }
  if (window.speechSynthesis) {
    window.speechSynthesis.onvoiceschanged = loadBestVoice;
    loadBestVoice();
  }

  /* ══════════════════════════════════════════════════════════════
     INIT
  ══════════════════════════════════════════════════════════════ */
  function init() {
    renderRoleBadge(currentRole);
    showWelcome(currentRole);
    renderChips(currentRole);
    bindEvents();
    fetchStatus();
    restoreHistory();
    setTimeout(function () { if (!isOpen) fabDot.style.display = 'block'; }, 3000);
  }

  function fetchStatus() {
    fetch(STATUS_API_URL)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.role && data.role !== currentRole) {
          currentRole = data.role;
          renderRoleBadge(currentRole);
          renderChips(currentRole);
          if (!msgContainer.querySelectorAll('.foi-msg:not(#foi-typing)').length) {
            showWelcome(currentRole);
          }
        }
      })
      .catch(function () {});
  }

  function renderRoleBadge(role) {
    roleLabel.textContent = (ROLE_CONFIG[role] || ROLE_CONFIG.guest).label;
  }
  function showWelcome(role) {
    appendMessage('bot', (ROLE_CONFIG[role] || ROLE_CONFIG.guest).welcome);
  }
  function renderChips(role) {
    var chips = (ROLE_CONFIG[role] || ROLE_CONFIG.guest).chips;
    suggsEl.innerHTML = '';
    chips.forEach(function (text) {
      var btn = document.createElement('button');
      btn.className   = 'foi-chip';
      btn.textContent = text;
      btn.addEventListener('click', function (e) { e.stopPropagation(); sendMessage(text); });
      suggsEl.appendChild(btn);
    });
  }

  /* ══════════════════════════════════════════════════════════════
     EVENT BINDING
  ══════════════════════════════════════════════════════════════ */
  function bindEvents() {
    fab.addEventListener('click', toggleChat);
    closeBtn.addEventListener('click', closeChat);
    clearBtn.addEventListener('click', clearChat);
    sendBtn.addEventListener('click', function () { sendMessage(); });
    voiceBtn.addEventListener('click', toggleVoice);
    inputEl.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    inputEl.addEventListener('input', autoResize);
    document.addEventListener('click', function (e) {
      if (!isOpen) return;
      if (e.target === fab) return;
      if (chatWin.contains(e.target)) return;
      /* Guard: target was removed from DOM (e.g. chip cleared itself) */
      if (!document.body.contains(e.target)) return;
      closeChat();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && isOpen) closeChat();
    });
  }

  /* ══════════════════════════════════════════════════════════════
     OPEN / CLOSE
  ══════════════════════════════════════════════════════════════ */
  function toggleChat() { isOpen ? closeChat() : openChat(); }
  function openChat() {
    isOpen = true;
    chatWin.classList.add('foi-open');
    fab.setAttribute('aria-expanded', 'true');
    fabDot.style.display = 'none';
    setTimeout(function () { inputEl.focus(); }, 300);
    scrollBottom();
  }
  function closeChat() {
    isOpen = false;
    chatWin.classList.remove('foi-open');
    fab.setAttribute('aria-expanded', 'false');
  }

  /* ══════════════════════════════════════════════════════════════
     VENDOR ROUTING
  ══════════════════════════════════════════════════════════════ */
  var SKIP_TRIGGERS = [
    'compare', 'pricing', 'price compare', 'competitor',
    'improve', 'suggestion', 'tip', 'how to',
    'what is', 'kya hai', 'kaise', 'hello', 'hi ', 'hey',
    'thank', 'okay', 'ok ', 'great', 'good', 'nice',
    'how are', 'who is', 'what are', 'tell me about',
  ];
  var COMPARE_TRIGGERS = [
    'compare', 'competitor', 'pricing', 'price compare',
    'market price', 'how much others', 'competitor price',
    'compare my price', 'compare pricing',
  ];
  var ORDER_TRIGGERS = [
    'track', 'my order', 'order status', 'where is my', 'order history',
    'past order', 'previous order', 'track my order', 'order tracking',
    'what happened to my order', 'my food',
  ];
  var REORDER_TRIGGERS = [
    'reorder', 'order again', 'same as before', 'my favourite',
    'my usual', 'what i ordered', 'order my usual', 'reorder favourites',
    'order favourites',
  ];
  var NEARBY_TRIGGERS = [
    'nearby', 'near me', 'restaurants near', 'find restaurant',
    'show restaurant', 'what restaurant', 'restaurants around',
    'food near', 'places near', 'find food', 'discover restaurant',
    'browse restaurant', 'all restaurant', 'available restaurant',
  ];

  function isOrderTrackRequest(text) {
    if (currentRole !== 'customer') return false;
    var lower = text.toLowerCase();
    return ORDER_TRIGGERS.some(function (kw) { return lower.indexOf(kw) !== -1; });
  }
  function isReorderRequest(text) {
    if (currentRole !== 'customer') return false;
    var lower = text.toLowerCase();
    return REORDER_TRIGGERS.some(function (kw) { return lower.indexOf(kw) !== -1; });
  }
  function isNearbyRequest(text) {
    if (currentRole === 'vendor') return false;
    var lower = text.toLowerCase();
    return NEARBY_TRIGGERS.some(function (kw) { return lower.indexOf(kw) !== -1; });
  }
  function isFoodGenRequest(text) {
    if (currentRole !== 'vendor') return false;
    var lower = text.toLowerCase();
    return !SKIP_TRIGGERS.some(function (kw) { return lower.indexOf(kw) !== -1; });
  }
  function isCompareRequest(text) {
    if (currentRole !== 'vendor') return false;
    var lower = text.toLowerCase();
    return COMPARE_TRIGGERS.some(function (kw) { return lower.indexOf(kw) !== -1; });
  }
  function isFoodRecommendRequest(text) {
    if (currentRole !== 'customer') return false;
    var lower = text.toLowerCase();
    var SKIP = ['hello', 'hi ', 'hey', 'thank', 'okay', 'ok ', 'how are', 'who are'];
    if (SKIP.some(function (kw) { return lower.indexOf(kw) !== -1; })) return false;
    var SIGNALS = [
      'food', 'eat', 'hungry', 'craving', 'want', 'meal', 'dish',
      'recommend', 'suggest', 'find', 'show me', 'feeling', 'mood',
      'spicy', 'sweet', 'healthy', 'light', 'heavy', 'snack',
      'breakfast', 'lunch', 'dinner', 'biryani', 'pizza', 'burger',
      'something', 'anything', 'what', 'veg', 'non veg', 'vegan',
    ];
    return SIGNALS.some(function (kw) { return lower.indexOf(kw) !== -1; });
  }
  /* ══════════════════════════════════════════════════════════════
     SEND MESSAGE
  ══════════════════════════════════════════════════════════════ */
  function sendMessage(overrideText) {
    var text = (overrideText !== undefined ? overrideText : inputEl.value).trim();
    if (!text || isTyping) return;

    if (currentRole === 'vendor' && isCompareRequest(text)) {
      inputEl.value = ''; inputEl.style.height = 'auto';
      appendMessage('user', text);
      suggsEl.style.display = 'none';
      triggerPriceComparison();
      return;
    }
    if (currentRole === 'customer' && isOrderTrackRequest(text)) {
      inputEl.value = ''; inputEl.style.height = 'auto';
      appendMessage('user', text);
      suggsEl.style.display = 'none';
      triggerOrderTracking();
      return;
    }
    if (currentRole === 'customer' && isReorderRequest(text)) {
      inputEl.value = ''; inputEl.style.height = 'auto';
      appendMessage('user', text);
      suggsEl.style.display = 'none';
      triggerReorderSuggestions();
      return;
    }
    if (isNearbyRequest(text)) {
      inputEl.value = ''; inputEl.style.height = 'auto';
      appendMessage('user', text);
      suggsEl.style.display = 'none';
      triggerNearbyRestaurants();
      return;
    }
    if (currentRole === 'customer' && isFoodRecommendRequest(text)) {
      inputEl.value = ''; inputEl.style.height = 'auto';
      appendMessage('user', text);
      suggsEl.style.display = 'none';
      triggerFoodRecommendations(text);
      return;
    }
    if (currentRole === 'vendor' && isFoodGenRequest(text)) {
      inputEl.value = ''; inputEl.style.height = 'auto';
      appendMessage('user', text);
      suggsEl.style.display = 'none';
      triggerFoodItemGenerator(text);
      return;
    }

    appendMessage('user', text);
    inputEl.value        = '';
    inputEl.style.height = 'auto';
    setTyping(true);
    sendBtn.disabled      = true;
    suggsEl.style.display = 'none';

    fetch(CHAT_API_URL, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
      body:    JSON.stringify({ message: text, session_key: sessionKey }),
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      setTyping(false);
      sendBtn.disabled = false;
      if (data.success) {
        if (data.session_key) {
          sessionKey = data.session_key;
          localStorage.setItem('foi_session_key', sessionKey);
        }
        appendMessage('bot', data.reply);
        speakReply(data.reply);
        showRoleChips();
      } else {
        appendMessage('bot', '⚠️ Something went wrong. Please try again.');
      }
    })
    .catch(function () {
      setTyping(false);
      sendBtn.disabled = false;
      appendMessage('bot', '⚠️ Connection error. Please check your internet and try again.');
    });
  }

  /* ══════════════════════════════════════════════════════════════
     MESSAGE RENDERING
  ══════════════════════════════════════════════════════════════ */
  function appendMessage(role, text) {
    var wrapper = document.createElement('div');
    wrapper.className = 'foi-msg foi-' + (role === 'user' ? 'user' : 'bot');
    var bubble = document.createElement('div');
    bubble.className   = 'foi-bubble';
    bubble.textContent = text;
    var time = document.createElement('div');
    time.className   = 'foi-msg-time';
    time.textContent = formatTime(new Date());
    wrapper.appendChild(bubble);
    wrapper.appendChild(time);
    msgContainer.insertBefore(wrapper, typingEl);
    scrollBottom();
  }

  function setTyping(show) {
    isTyping = show;
    typingEl.style.display = show ? 'flex' : 'none';
    if (show) scrollBottom();
  }
  function scrollBottom() {
    requestAnimationFrame(function () { msgContainer.scrollTop = msgContainer.scrollHeight; });
  }
  function autoResize() {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 90) + 'px';
  }
  function formatTime(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  /* ══════════════════════════════════════════════════════════════
     CLEAR CHAT
  ══════════════════════════════════════════════════════════════ */
  function clearChat() {
    if (!confirm('Start a new conversation?')) return;
    if (sessionKey) {
      fetch(CLEAR_API_URL, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        body:    JSON.stringify({ session_key: sessionKey }),
      }).catch(function () {});
    }
    sessionKey = '';
    localStorage.removeItem('foi_session_key');
    Array.prototype.slice.call(msgContainer.children).forEach(function (c) {
      if (c.id !== 'foi-typing') msgContainer.removeChild(c);
    });
    typingEl.style.display = 'none';
    suggsEl.style.display  = 'flex';
    showWelcome(currentRole);
    renderChips(currentRole);
  }

  /* ══════════════════════════════════════════════════════════════
     RESTORE HISTORY
  ══════════════════════════════════════════════════════════════ */
  function restoreHistory() {
    if (!IS_AUTH || !sessionKey) return;
    fetch(HISTORY_API_URL + '?session_key=' + encodeURIComponent(sessionKey))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success && data.messages && data.messages.length > 0) {
          Array.prototype.slice.call(msgContainer.children).forEach(function (c) {
            if (c.id !== 'foi-typing') msgContainer.removeChild(c);
          });
          data.messages.forEach(function (m) { appendMessage(m.role, m.content); });
          suggsEl.style.display = 'none';
        }
      })
      .catch(function () {});

    /* Keepalive — ping every 4 minutes to prevent session expiry */
    setInterval(function () {
      if (!sessionKey) return;
      fetch(HISTORY_API_URL + '?session_key=' + encodeURIComponent(sessionKey))
        .catch(function () {});
    }, 4 * 60 * 1000);
  }

  /* ══════════════════════════════════════════════════════════════
     VOICE INPUT
  ══════════════════════════════════════════════════════════════ */
  function toggleVoice() {
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      appendMessage('bot', "🎤 Voice input isn't supported in your browser. Try Chrome or Edge!");
      return;
    }
    if (isListening) { if (recognition) recognition.stop(); return; }

    recognition = new SR();
    recognition.lang            = 'en-IN';
    recognition.interimResults  = false;
    recognition.maxAlternatives = 1;

    recognition.onstart  = function () {
      isListening = true;
      voiceBtn.classList.add('foi-listening');
      inputEl.placeholder = '🎤 Listening…';
    };
    recognition.onresult = function (e) {
      inputEl.value = e.results[0][0].transcript;
      autoResize();
    };
    recognition.onerror  = function (e) { console.warn('Speech error:', e.error); };
    recognition.onend    = function () {
      isListening = false;
      voiceBtn.classList.remove('foi-listening');
      inputEl.placeholder = 'Ask me anything about food…';
    };
    recognition.start();
  }

  /* ══════════════════════════════════════════════════════════════
     VOICE OUTPUT
  ══════════════════════════════════════════════════════════════ */
  function speakReply(text) {
    if (!window.speechSynthesis || !text) return;
    var clean = text
      .replace(/\*\*(.*?)\*\*/g, '$1').replace(/\*(.*?)\*/g, '$1')
      .replace(/#+\s/g, '').replace(/[₹$€]/g, ' rupees ').trim();
    if (clean.length > 250) clean = clean.substring(0, 250) + '…';
    window.speechSynthesis.cancel();
    var u = new SpeechSynthesisUtterance(clean);
    if (preferredVoice) u.voice = preferredVoice;
    u.lang = 'en-US'; u.rate = 0.95; u.pitch = 1.05; u.volume = 0.9;
    window.speechSynthesis.speak(u);
  }

  /* ══════════════════════════════════════════════════════════════
     PHASE 2 — FOOD ITEM GENERATOR
  ══════════════════════════════════════════════════════════════ */
  function triggerFoodItemGenerator(prompt) {
    setTyping(true);
    sendBtn.disabled = true;

    fetch('/ai/generate-food-item/', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
      body:    JSON.stringify({ prompt: prompt }),
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      setTyping(false);
      sendBtn.disabled = false;
      if (data.success) {
        appendMessage('bot', '✨ Here\'s your AI-generated menu item! Review and edit before saving:');
        appendFoodCard(data.item);
      } else {
        appendMessage('bot', '❌ Couldn\'t generate item: ' + (data.error || 'Unknown error'));
      }
    })
    .catch(function () {
      setTyping(false);
      sendBtn.disabled = false;
      appendMessage('bot', '❌ Network error while generating item. Please try again.');
    });
  }

  /* ══════════════════════════════════════════════════════════════
     PHASE 3 — PRICE COMPARISON
     Handles every possible backend response:
       • HTTP error (403, 404, 500)  → show error message
       • success:false               → show error from backend
       • success:true, no items      → tell vendor to add items
       • success:true, no competitor → summary explains, no table
       • success:true, has data      → summary + table
  ══════════════════════════════════════════════════════════════ */
  function triggerPriceComparison() {
    setTyping(true);
    sendBtn.disabled = true;

    fetch('/ai/compare-pricing/', {
      method:  'GET',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
    })
    .then(function (r) {
      /* Always parse JSON, but flag non-2xx so we can handle it below */
      return r.json().then(function (data) {
        return { ok: r.ok, status: r.status, data: data };
      });
    })
    .then(function (res) {
      setTyping(false);
      sendBtn.disabled = false;

      /* HTTP-level error (403 vendor check, 404 no profile, 500, etc.) */
      if (!res.ok) {
        var msg = (res.data && res.data.error)
          ? '❌ ' + res.data.error
          : '❌ Server error (' + res.status + '). Please try again.';
        appendMessage('bot', msg);
        return;
      }

      var data = res.data;

      /* Backend returned success:false */
      if (!data.success) {
        appendMessage('bot', '❌ ' + (data.error || 'Could not fetch pricing data.'));
        return;
      }

      /* Always show the summary first — backend guarantees a useful string */
      if (data.summary) {
        appendMessage('bot', data.summary);
      }

      /* Only render the table if there is actual competitor data */
      if (data.data) {
        appendPriceTable(data.data);
      }
    })
    .catch(function (err) {
      /* Network failure, JSON parse error, etc. */
      setTyping(false);
      sendBtn.disabled = false;
      console.error('[FoodOnline AI] Price comparison error:', err);
      appendMessage('bot', '❌ Could not reach the server. Please check your connection and try again.');
    });
  }

  function appendPriceTable(data) {
    if (!data || !data.items || !data.items.length) return;

    /* Only render rows that have competitor data */
    var comparableItems = data.items.filter(function (i) {
      return i.competitor_avg !== null && i.competitor_avg !== undefined;
    });

    /* No comparable items — backend summary already told the vendor, skip table */
    if (!comparableItems.length) return;

    var rows = comparableItems.map(function (item) {
      var icon = item.status === 'expensive' ? '🔴'
               : item.status === 'cheap'     ? '🟡'
               : '🟢';
      return '<tr>' +
        '<td>' + escHtml(item.title) + '</td>' +
        '<td>₹' + Number(item.my_price).toFixed(2) + '</td>' +
        '<td>₹' + Number(item.competitor_avg).toFixed(2) + '</td>' +
        '<td>₹' + Number(item.competitor_min).toFixed(2) +
             '–₹' + Number(item.competitor_max).toFixed(2) + '</td>' +
        '<td>' + icon + ' ' + escHtml(item.status) + '</td>' +
        '</tr>';
    }).join('');

    var wrap = document.createElement('div');
    wrap.className = 'foi-price-table-wrap';
    wrap.innerHTML =
      '<div class="foi-price-table-title">📋 ' +
        escHtml(data.vendor_name || 'Your Menu') + ' — ' +
        escHtml(data.city || 'Your City') +
      '</div>' +
      '<table class="foi-price-table"><thead><tr>' +
        '<th>Item</th><th>My Price</th><th>Mkt Avg</th><th>Range</th><th>Status</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table>' +
      '<div class="foi-price-legend">🟢 Competitive &nbsp; 🔴 Expensive &nbsp; 🟡 Below Market</div>';

    msgContainer.insertBefore(wrap, typingEl);
    scrollBottom();
  }

  /* ══════════════════════════════════════════════════════════════
     PHASE 2 — FOOD CARD
     Image button row now has FOUR options:
       🔄 Change Image  — re-runs AI provider chain
       📁 Upload Image  — vendor picks their own photo (NEW)
       ❌ No Image      — clears & skips image entirely
  ══════════════════════════════════════════════════════════════ */
  function appendFoodCard(item) {
    var tagsStr = Array.isArray(item.tags) ? item.tags.join(', ') : (item.tags || '');

    var card = document.createElement('div');
    card.className         = 'food-gen-card';
    card.dataset.imageUrl  = '';
    card.dataset.skipImage = 'false';
    card.dataset.attempt   = '0';

    card.innerHTML = [
      '<div class="fgc-header">',
      '  <span class="fgc-icon">🍽️</span>',
      '  <span class="fgc-label">AI Menu Item — Edit &amp; Save</span>',
      '</div>',

      '<div class="fgc-img-preview">',
      '</div>',

      '<div class="fgc-img-btns">',
      '  <label class="fgc-btn fgc-btn-upload-label fgc-btn-upload-primary" title="Upload your own photo">',
      '    📷 Add Photo',
      '    <input class="fgc-upload-input" type="file" accept="image/*" style="display:none" />',
      '  </label>',
      '  <button class="fgc-btn fgc-btn-skip-img" type="button">⏭️ Skip</button>',
      '</div>',
      /* ───────────────────────────────────────────────────────── */

      '<div class="fgc-field"><label>Title</label>',
      '  <input class="fgc-input fgc-title" type="text" value="' + escHtml(item.title) + '" /></div>',

      '<div class="fgc-field"><label>Description</label>',
      '  <textarea class="fgc-input fgc-desc" rows="3">' + escHtml(item.description) + '</textarea></div>',

      '<div class="fgc-row">',
      '  <div class="fgc-field"><label>Category</label>',
      '    <input class="fgc-input fgc-category" type="text" value="' + escHtml(item.category) + '" /></div>',
      '  <div class="fgc-field"><label>Price (₹)</label>',
      '    <input class="fgc-input fgc-price" type="number" min="0" step="0.5" value="' + (item.price || 0) + '" /></div>',
      '</div>',

      '<div class="fgc-field"><label>Tags <span class="fgc-hint">(comma-separated)</span></label>',
      '  <input class="fgc-input fgc-tags" type="text" value="' + escHtml(tagsStr) + '" /></div>',

      '<div class="fgc-actions">',
      '  <button class="fgc-btn fgc-btn-save" type="button">💾 Save to Menu</button>',
      '  <button class="fgc-btn fgc-btn-discard" type="button">🗑️ Discard</button>',
      '</div>',

      '<div class="fgc-status"></div>',
    ].join('');



    /* ── 📁 Upload Image (NEW) ─────────────────────────────────── */
    card.querySelector('.fgc-upload-input').addEventListener('change', function (e) {
      var file = e.target.files[0];
      if (!file) return;

      /* Reset the input so the same file can be re-chosen if needed */
      e.target.value = '';

      var statusEl = card.querySelector('.fgc-status');

      /* Validate file type */
      if (!file.type.startsWith('image/')) {
        statusEl.textContent = '⚠️ Please select a valid image file (JPG, PNG, WEBP, etc.).';
        statusEl.style.color = '#c0392b';
        return;
      }

      /* Validate file size — 5 MB cap */
      if (file.size > 5 * 1024 * 1024) {
        statusEl.textContent = '⚠️ Image must be under 5 MB. Please choose a smaller file.';
        statusEl.style.color = '#c0392b';
        return;
      }

      /* Clear any old status message */
      statusEl.textContent = '';

      /* Show a brief "loading" state while reading the file */
      var previewEl = card.querySelector('.fgc-img-preview');
      previewEl.innerHTML = [
        '<div class="fgc-img-loading">',
        '  <div class="fgc-img-spinner"></div>',
        '  <span>Loading your photo…</span>',
        '</div>',
      ].join('');

      var reader = new FileReader();

      reader.onload = function (ev) {
        var dataUrl = ev.target.result;

        /* Store the data-URL — saveFoodCard reads card.dataset.imageUrl */
        card.dataset.imageUrl  = dataUrl;
        card.dataset.skipImage = 'false';

        /* Render the uploaded image in the preview slot */
        var wrapper = document.createElement('div');
        wrapper.className = 'fgc-img-wrapper';

        var imgEl       = document.createElement('img');
        imgEl.src       = dataUrl;
        imgEl.alt       = card.querySelector('.fgc-title').value || 'Food photo';
        imgEl.className = 'fgc-img-result';

        var caption           = document.createElement('div');
        caption.className     = 'fgc-img-caption fgc-img-caption--upload';
        caption.textContent   = '📁 Your photo — looking great! You can still swap it below.';

        wrapper.appendChild(imgEl);
        wrapper.appendChild(caption);
        previewEl.innerHTML = '';
        previewEl.appendChild(wrapper);

        /* Keep the action buttons visible */
        card.querySelector('.fgc-img-btns').style.display = 'flex';
        scrollBottom();
      };

      reader.onerror = function () {
        statusEl.textContent = '❌ Could not read the file. Please try again.';
        statusEl.style.color = '#c0392b';
        /* Restore the previous preview so user isn't left with a blank slot */
        autoGenerateImage(card);
      };

      reader.readAsDataURL(file);
    });

    /* ── ⏭️ Skip Image ─────────────────────────────────────────── */
    card.querySelector('.fgc-btn-skip-img').addEventListener('click', function () {
      var confirmed = confirm(
        '⚠️ Skipping the photo?\n\n' +
        'Items with photos get significantly more clicks on FoodOnline.\n\n' +
        'You can add one now by clicking "Add Photo", or later from your vendor dashboard under Menu → Edit Item.\n\n' +
        'Skip anyway?'
      );
      if (!confirmed) return;

      card.dataset.imageUrl  = '';
      card.dataset.skipImage = 'true';
      card.querySelector('.fgc-img-preview').innerHTML =
        '<div class="fgc-img-skipped">' +
        '  ⏭️ No image added — go to <strong>Menu → Edit Item</strong> in your dashboard to add one later.' +
        '</div>';
      card.querySelector('.fgc-img-btns').style.display = 'none';
    });

    /* ── 💾 Save / 🗑️ Discard ─────────────────────────────────── */
    card.querySelector('.fgc-btn-save').addEventListener('click', function () {
      saveFoodCard(card);
    });
    card.querySelector('.fgc-btn-discard').addEventListener('click', function () {
      discardFoodCard(card);
    });

    msgContainer.insertBefore(card, typingEl);
    scrollBottom();

    /* Show upload prompt instead of AI generation */
    showImageUploadPrompt(card);
  }

  /* ══════════════════════════════════════════════════════════════
     PHASE 4 — IMAGE UPLOAD PROMPT
  ══════════════════════════════════════════════════════════════ */
  function showImageUploadPrompt(card) {
    var previewEl = card.querySelector('.fgc-img-preview');
    if (!previewEl) return;
    previewEl.innerHTML = [
      '<div class="fgc-img-upload-prompt">',
      '  <div class="fgc-img-upload-icon">📷</div>',
      '  <div class="fgc-img-upload-text">Add a photo of your dish</div>',
      '  <div class="fgc-img-upload-sub">Customers love seeing what they\'re ordering!</div>',
      '</div>',
    ].join('');
  }

  function autoGenerateImage(card) {
    var previewEl  = card.querySelector('.fgc-img-preview');
    var imgBtns    = card.querySelector('.fgc-img-btns');
    var titleInput = card.querySelector('.fgc-title');
    var descInput  = card.querySelector('.fgc-desc');

    if (!titleInput || !previewEl) return;

    var title   = titleInput.value.trim();
    var desc    = descInput ? descInput.value.trim() : '';
    var attempt = parseInt(card.dataset.attempt || '0', 10);

    if (!title) {
      previewEl.innerHTML = '<div class="fgc-img-error">⚠️ Add a title first.</div>';
      if (imgBtns) imgBtns.style.display = 'flex';
      return;
    }

    card.dataset.imageUrl = '';

    previewEl.innerHTML = [
      '<div class="fgc-img-loading">',
      '  <div class="fgc-img-spinner"></div>',
      '  <span>Generating image…</span>',
      '</div>',
    ].join('');

    /* Keep buttons visible throughout so user can always upload/skip */
    if (imgBtns) imgBtns.style.display = 'flex';

    tryImageProviders(title, desc, attempt)
      .then(function (url) {
        card.dataset.imageUrl = url;

        var wrapper = document.createElement('div');
        wrapper.className = 'fgc-img-wrapper';

        var imgEl = document.createElement('img');
        imgEl.src       = url;
        imgEl.alt       = title;
        imgEl.className = 'fgc-img-result';

        var caption = document.createElement('div');
        caption.className   = 'fgc-img-caption';
        caption.textContent = '🖼️ AI-generated — not quite right? Upload your own photo below.';

        wrapper.appendChild(imgEl);
        wrapper.appendChild(caption);
        previewEl.innerHTML = '';
        previewEl.appendChild(wrapper);

        if (imgBtns) imgBtns.style.display = 'flex';
        scrollBottom();
      })
      .catch(function () {
        /* Only reachable if Canvas also fails — should never happen */
        card.dataset.imageUrl = '';
        previewEl.innerHTML = [
          '<div class="fgc-img-error">',
          '  ❌ Could not generate an image. ',
          '  <button class="fgc-btn-retry-img" type="button">Retry</button>',
          '</div>',
        ].join('');
        var retry = previewEl.querySelector('.fgc-btn-retry-img');
        if (retry) {
          retry.addEventListener('click', function () {
            card.dataset.attempt = String(parseInt(card.dataset.attempt || '0', 10) + 1);
            autoGenerateImage(card);
          });
        }
        if (imgBtns) imgBtns.style.display = 'flex';
        scrollBottom();
      });
  }

  /* ══════════════════════════════════════════════════════════════
     PHASE 2 — SAVE FOOD CARD
  ══════════════════════════════════════════════════════════════ */
  function saveFoodCard(card) {
    var statusEl = card.querySelector('.fgc-status');
    var saveBtn  = card.querySelector('.fgc-btn-save');

    var skipImage = card.dataset.skipImage === 'true';
    var payload   = {
      title:       card.querySelector('.fgc-title').value.trim(),
      description: card.querySelector('.fgc-desc').value.trim(),
      category:    card.querySelector('.fgc-category').value.trim(),
      price:       parseFloat(card.querySelector('.fgc-price').value) || 0,
      tags:        card.querySelector('.fgc-tags').value
                       .split(',').map(function (t) { return t.trim(); }).filter(Boolean),
      image_url:   skipImage ? '' : (card.dataset.imageUrl || ''),
    };

    if (!payload.title) {
      statusEl.textContent = '⚠️ Title is required before saving.';
      statusEl.style.color = '#c0392b'; return;
    }
    if (!payload.category) {
      statusEl.textContent = '⚠️ Category is required before saving.';
      statusEl.style.color = '#c0392b'; return;
    }
    if (isNaN(payload.price) || payload.price < 0) {
      statusEl.textContent = '⚠️ Please enter a valid price.';
      statusEl.style.color = '#c0392b'; return;
    }

    saveBtn.disabled     = true;
    saveBtn.textContent  = '⏳ Saving…';
    statusEl.textContent = '';

    fetch('/ai/save-food-item/', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
      body:    JSON.stringify(payload),
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.success) {
        statusEl.textContent = '✅ "' + payload.title + '" added to your menu!';
        statusEl.style.color = '#27ae60';
        saveBtn.textContent  = '✅ Saved';
        setTimeout(function () {
          card.style.opacity    = '0';
          card.style.transform  = 'scale(0.95)';
          card.style.transition = 'all 0.3s ease';
          setTimeout(function () {
            card.remove();
              appendMessage('bot', '🎉 "' + payload.title + '" has been added to your menu! What would you like to do next?');
              renderPostCardChips(payload.title, payload.category);
            suggsEl.style.display = 'flex';
          }, 300);
        }, 1500);
      } else {
        statusEl.textContent = '❌ ' + (data.error || 'Save failed. Please try again.');
        statusEl.style.color = '#c0392b';
        saveBtn.disabled     = false;
        saveBtn.textContent  = '💾 Save to Menu';
      }
    })
    .catch(function () {
      statusEl.textContent = '❌ Network error. Please check your connection and try again.';
      statusEl.style.color = '#c0392b';
      saveBtn.disabled     = false;
      saveBtn.textContent  = '💾 Save to Menu';
    });
  }

  /* ══════════════════════════════════════════════════════════════
     PHASE 2 — DISCARD FOOD CARD
  ══════════════════════════════════════════════════════════════ */
  function discardFoodCard(card) {
    card.style.opacity    = '0';
    card.style.transform  = 'scale(0.95)';
    card.style.transition = 'all 0.25s ease';
    setTimeout(function () {
      
    card.remove();
      appendMessage('bot', '🗑️ No worries! Here are some ideas for what to add next:');
      renderPostCardChips(null, null);
    }, 260);
  }

  /* ══════════════════════════════════════════════════════════════
     HTML ESCAPE HELPER
  ══════════════════════════════════════════════════════════════ */
  /* ══════════════════════════════════════════════════════════════
     PHASE 7 — ADD TO CART (AJAX)
  ══════════════════════════════════════════════════════════════ */
  function addToCart(foodId, btn) {
    var originalText = btn.textContent;
    btn.disabled    = true;
    btn.textContent = '⏳ Adding…';

    fetch('/marketplace/add_to_cart/' + foodId + '/', {
      method:  'GET',
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken') },
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.status === 'login_required') {
        btn.disabled    = false;
        btn.textContent = originalText;
        appendMessage('bot', '🔐 Please log in to add items to your cart!');
        return;
      }
      if (data.status === 'restaurant_closed') {
        btn.disabled    = false;
        btn.textContent = originalText;
        appendMessage('bot', '🚫 This restaurant is currently closed. Try again when they open!');
        return;
      }
      if (data.status === 'success') {
        btn.textContent  = '✅ Added!';
        btn.style.background = '#27ae60';
        /* Update cart counter badge in the main navbar if it exists */
        var counter = document.querySelector('.cart_counter');
        if (counter && data.cart_counter) {
          var count = data.cart_counter['cart_count'] || 0;
          counter.textContent = count;
        }
        setTimeout(function () {
          btn.disabled    = false;
          btn.textContent = '🛒 Add to Cart';
          btn.style.background = '';
        }, 2000);
      } else {
        btn.disabled    = false;
        btn.textContent = originalText;
        appendMessage('bot', '⚠️ ' + (data.message || 'Could not add to cart. Please try again.'));
      }
    })
    .catch(function () {
      btn.disabled    = false;
      btn.textContent = originalText;
      appendMessage('bot', '❌ Connection error. Please try again.');
    });
  }

  /* ══════════════════════════════════════════════════════════════
     PHASE 7 — VENDOR CONTACT INFO PANEL
  ══════════════════════════════════════════════════════════════ */
  function triggerVendorInfo(vendorId, vendorName, card) {
    /* Toggle: if panel already open, close it */
    var existing = card.querySelector('.foi-vendor-info-panel');
    if (existing) {
      existing.remove();
      return;
    }

    var panel = document.createElement('div');
    panel.className = 'foi-vendor-info-panel';
    panel.innerHTML = '<div class="foi-vendor-info-loading">⏳ Loading contact info…</div>';
    card.appendChild(panel);
    scrollBottom();

    fetch('/ai/vendor-info/' + vendorId + '/', { method: 'GET' })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (!data.success) {
        panel.innerHTML = '<div class="foi-vendor-info-error">❌ Could not load info.</div>';
        return;
      }
      var v = data.vendor;

      /* Open/closed badge */
      var statusBadge = v.is_open
        ? '<span class="foi-vi-open">🟢 Open Now</span>'
        : '<span class="foi-vi-closed">🔴 Closed Now</span>';

      /* Contact rows */
      var contactRows = '';
      if (v.phone) {
        contactRows += '<a class="foi-vi-row" href="tel:' + escHtml(v.phone) + '">' +
          '<span class="foi-vi-icon">📞</span><span>' + escHtml(v.phone) + '</span></a>';
      }
      if (v.email) {
        contactRows += '<a class="foi-vi-row" href="mailto:' + escHtml(v.email) + '">' +
          '<span class="foi-vi-icon">✉️</span><span>' + escHtml(v.email) + '</span></a>';
      }
      if (v.address) {
        var fullAddr = [v.address, v.city, v.state, v.pincode].filter(Boolean).join(', ');
        contactRows += '<div class="foi-vi-row">' +
          '<span class="foi-vi-icon">📍</span><span>' + escHtml(fullAddr) + '</span></div>';
      }

      /* Opening hours */
      var hoursRows = '';
      if (v.hours && v.hours.length) {
        hoursRows = '<div class="foi-vi-section-title">🕐 Opening Hours</div>';
        v.hours.forEach(function (h) {
          hoursRows += '<div class="foi-vi-hours-row">' +
            '<span class="foi-vi-day">' + escHtml(h.day) + '</span>' +
            '<span class="foi-vi-time">' +
              (h.is_closed ? '<em>Closed</em>' : escHtml(h.from_hour) + ' – ' + escHtml(h.to_hour)) +
            '</span>' +
          '</div>';
        });
      }

      panel.innerHTML = [
        '<div class="foi-vi-header">',
        '  <strong>' + escHtml(v.name) + '</strong>',
        '  ' + statusBadge,
        '</div>',
        '<div class="foi-vi-contacts">' + (contactRows || '<em>No contact info available</em>') + '</div>',
        hoursRows ? '<div class="foi-vi-hours">' + hoursRows + '</div>' : '',
        '<div class="foi-vi-footer">',
        '  <a class="foi-vendor-btn" href="/marketplace/' + escHtml(v.slug) + '/" target="_blank">🛒 View Full Menu</a>',
        '</div>',
      ].join('');

      scrollBottom();
    })
    .catch(function () {
      panel.innerHTML = '<div class="foi-vendor-info-error">❌ Connection error.</div>';
    });
  }

  function escHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;').replace(/"/g, '&quot;')
      .replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }


  /* ══════════════════════════════════════════════════════════════
   POST-CARD SUGGESTION CHIPS
   Shows context-aware next-step chips after a card is saved
   or discarded, so the vendor always knows what to do next.
══════════════════════════════════════════════════════════════ */
function renderPostCardChips(savedTitle, savedCategory) {
  var CATEGORY_FOLLOWUPS = {
    'starters':    ['Add a soup 🍲', 'Add a dip or chutney 🫙', 'Add a salad 🥗'],
    'main course': ['Add a bread/roti 🫓', 'Add a rice dish 🍛', 'Add a gravy variant 🥘'],
    'desserts':    ['Add a cold dessert 🍨', 'Add a hot dessert 🍮', 'Add a drinks/lassi 🥛'],
    'beverages':   ['Add a mocktail 🍹', 'Add a hot drink ☕', 'Add a fresh juice 🍊'],
    'snacks':      ['Add a fried snack 🍟', 'Add a sandwich 🥪', 'Add a chaat item 🌮'],
    'breakfast':   ['Add a paratha 🫓', 'Add an egg dish 🍳', 'Add a breakfast combo 🍱'],
  };

  var GENERIC_CHIPS = [
    'Add a starter 🥗',
    'Add a main course 🍛',
    'Add a dessert 🍰',
    'Add a beverage 🥤',
    'Compare my pricing 💰',
    'Suggest categories 📋',
  ];

  suggsEl.innerHTML = '';
  suggsEl.style.display = 'flex';

  var chips = [];

  /* Context-aware suggestions based on saved category */
  if (savedCategory) {
    var catKey = savedCategory.toLowerCase().trim();
    var catChips = CATEGORY_FOLLOWUPS[catKey] || [];
    chips = chips.concat(catChips.slice(0, 2));
  }

  /* Always add a pricing compare + a generic filler */
  var generics = GENERIC_CHIPS.filter(function (c) {
    /* Don't repeat the category we just saved */
    return !savedCategory || c.toLowerCase().indexOf(savedCategory.toLowerCase()) === -1;
  });

  /* Fill up to 4 chips total */
  var i = 0;
  while (chips.length < 4 && i < generics.length) {
    chips.push(generics[i]);
    i++;
  }

  chips.forEach(function (text) {
    var btn = document.createElement('button');
    btn.className   = 'foi-chip foi-chip-suggestion';
    btn.textContent = text;
    btn.addEventListener('click', function () {
      suggsEl.innerHTML = '';
      suggsEl.style.display = 'none';
      sendMessage(text);
    });
    suggsEl.appendChild(btn);
  });
}

  /* ══════════════════════════════════════════════════════════════
     SHOW ROLE CHIPS — called after every bot response
  ══════════════════════════════════════════════════════════════ */
  function showRoleChips() {
    var CUSTOMER_CHIPS = [
      "I'm feeling spicy 🌶️",
      "Something healthy 🥗",
      "Restaurants near me 🗺️",
      "Track my orders 📦",
    ];
    var VENDOR_CHIPS = [
      'Generate a food item 🍱',
      'Compare my pricing 💰',
      'Suggest categories 📋',
      'Menu improvement tips ✨',
    ];
    var GUEST_CHIPS = [
      'How does FoodOnline work? 🤔',
      'Find restaurants 🗺️',
      'Register as a vendor 🏪',
      'Login to my account 🔐',
    ];
    var chips = currentRole === 'vendor' ? VENDOR_CHIPS
              : currentRole === 'customer' ? CUSTOMER_CHIPS
              : GUEST_CHIPS;

    suggsEl.innerHTML = '';
    suggsEl.style.display = 'flex';
    chips.forEach(function (text) {
      var btn = document.createElement('button');
      btn.className   = 'foi-chip';
      btn.textContent = text;
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        suggsEl.innerHTML = '';
        suggsEl.style.display = 'none';
        sendMessage(text);
      });
      suggsEl.appendChild(btn);
    });
  }

  /* ══════════════════════════════════════════════════════════════
     ORDER TRACKING
  ══════════════════════════════════════════════════════════════ */
  function triggerOrderTracking() {
    setTyping(true);
    sendBtn.disabled = true;

    fetch('/ai/orders/', { method: 'GET' })
    .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
    .then(function (res) {
      setTyping(false);
      sendBtn.disabled = false;

      if (!res.ok || !res.data.success) {
        appendMessage('bot', '❌ ' + (res.data.error || 'Could not load orders.'));
        showRoleChips();
        return;
      }

      if (!res.data.orders || !res.data.orders.length) {
        appendMessage('bot', res.data.message || "You haven't ordered yet!");
        showRoleChips();
        return;
      }

      appendMessage('bot', '📦 Here are your recent orders:');
      appendOrderCards(res.data.orders);
      showRoleChips();
    })
    .catch(function () {
      setTyping(false);
      sendBtn.disabled = false;
      appendMessage('bot', '❌ Connection error. Please try again.');
      showRoleChips();
    });
  }

  function appendOrderCards(orders) {
    var wrap = document.createElement('div');
    wrap.className = 'foi-order-list';

    orders.forEach(function (order) {
      var card = document.createElement('div');
      card.className = 'foi-order-card';

      /* Timeline dots */
      var timelineDots = order.timeline.map(function (step, i) {
        var active = step ? 'foi-tl-active' : 'foi-tl-inactive';
        return '<div class="foi-tl-step ' + active + '">' +
               '  <div class="foi-tl-dot"></div>' +
               (step ? '<div class="foi-tl-label">' + escHtml(step) + '</div>' : '') +
               '</div>';
      }).join('');

      /* Vendor blocks with contact */
      var vendorBlocks = order.vendors.map(function (v) {
        var contactHtml = '';
        if (v.phone) {
          contactHtml += '<a class="foi-order-contact-btn" href="tel:' + escHtml(v.phone) + '" target="_blank">📞 Call</a>';
        }
        if (v.email) {
          var subject = encodeURIComponent('Query about Order #' + order.order_number);
          var body = encodeURIComponent('Hi,\n\nI have a query regarding my order.\n\nOrder Number: ' + order.order_number + '\nPayment ID: ' + order.payment_id + '\n\nPlease look into this.\n\nThank you.');
          var gmailUrl = 'https://mail.google.com/mail/?view=cm&to=' + encodeURIComponent(v.email) + '&su=' + subject + '&body=' + body;
          contactHtml += '<a class="foi-order-contact-btn" href="' + gmailUrl + '" target="_blank" rel="noopener noreferrer">✉️ Email</a>';
        }
        var itemList = v.items.map(function (it) {
          return '<span class="foi-order-item-pill">' + escHtml(it.food_title) + ' x' + it.quantity + '</span>';
        }).join('');

        return '<div class="foi-order-vendor-block">' +
               '  <div class="foi-order-vendor-name">🏪 ' + escHtml(v.name) + '</div>' +
               '  <div class="foi-order-items">' + itemList + '</div>' +
               '  <div class="foi-order-contacts">' + contactHtml + '</div>' +
               '</div>';
      }).join('');

      card.innerHTML = [
        '<div class="foi-order-header">',
        '  <span class="foi-order-num">#' + escHtml(order.order_number) + '</span>',
        '  <span class="foi-order-status" style="background:' + escHtml(order.status_color) + '">',
        '    ' + escHtml(order.status_emoji) + ' ' + escHtml(order.status_label),
        '  </span>',
        '</div>',
        '<div class="foi-order-meta">',
        '  <span>📅 ' + escHtml(order.created_at) + '</span>',
        '  <span>💳 ' + escHtml(order.payment_method) + '</span>',
        '  <span>💰 ₹' + Number(order.total).toFixed(2) + '</span>',
        '</div>',
        '<div class="foi-order-timeline">' + timelineDots + '</div>',
        vendorBlocks,
      ].join('');

      wrap.appendChild(card);
    });

    msgContainer.insertBefore(wrap, typingEl);
    scrollBottom();
  }

  /* ══════════════════════════════════════════════════════════════
     SMART REORDER SUGGESTIONS
  ══════════════════════════════════════════════════════════════ */
  function triggerReorderSuggestions() {
    setTyping(true);
    sendBtn.disabled = true;

    fetch('/ai/reorder/', { method: 'GET' })
    .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
    .then(function (res) {
      setTyping(false);
      sendBtn.disabled = false;

      if (!res.ok || !res.data.success) {
        appendMessage('bot', '❌ ' + (res.data.error || 'Could not load suggestions.'));
        showRoleChips();
        return;
      }

      if (!res.data.items || !res.data.items.length) {
        appendMessage('bot', res.data.message || "No suggestions yet!");
        showRoleChips();
        return;
      }

      appendMessage('bot', "🧠 Based on what you've ordered before — here's what your stomach already knows it wants:");
      appendReorderCards(res.data.items);
      showRoleChips();
    })
    .catch(function () {
      setTyping(false);
      sendBtn.disabled = false;
      appendMessage('bot', '❌ Connection error. Please try again.');
      showRoleChips();
    });
  }

  function appendReorderCards(items) {
    var wrap = document.createElement('div');
    wrap.className = 'foi-rec-grid';

    items.forEach(function (item) {
      var card = document.createElement('div');
      card.className = 'foi-rec-card foi-reorder-card';

      var imgHtml = item.image_url
        ? '<img class="foi-rec-img" src="' + escHtml(item.image_url) + '" alt="' + escHtml(item.food_title) + '" onerror="this.style.display=\'none\';this.nextSibling.style.display=\'flex\'" />'
          + '<div class="foi-rec-img-placeholder" style="display:none">🍽️</div>'
        : '<div class="foi-rec-img-placeholder">🍽️</div>';

      card.innerHTML = [
        '<div class="foi-reorder-badge">🔄 Ordered ' + item.order_count + 'x</div>',
        '<div class="foi-rec-img-wrap">' + imgHtml + '</div>',
        '<div class="foi-rec-body">',
        '  <div class="foi-reorder-copy-title">' + escHtml(item.copy_title) + '</div>',
        '  <div class="foi-reorder-copy-sub">' + escHtml(item.copy_sub) + '</div>',
        '  <div class="foi-rec-title">' + escHtml(item.food_title) + '</div>',
        '  <div class="foi-rec-vendor">🏪 ' + escHtml(item.vendor_name) + '</div>',
        '  <div class="foi-rec-meta">',
        '    <span class="foi-rec-category">' + escHtml(item.category) + '</span>',
        '    <span class="foi-rec-price">₹' + Number(item.price).toFixed(0) + '</span>',
        '  </div>',
        '</div>',
        '<div class="foi-rec-footer foi-rec-footer--two">',
        '  <a class="foi-rec-order-btn foi-rec-btn-secondary" href="/marketplace/' + escHtml(item.vendor_slug) + '/" target="_blank">',
        '    🍽️ View Menu',
        '  </a>',
        '  <button class="foi-rec-order-btn foi-rec-btn-primary foi-add-cart-btn" data-food-id="' + item.id + '">',
        '    🛒 Add to Cart',
        '  </button>',
        '</div>',
      ].join('');

      wrap.appendChild(card);
    });

    /* Wire Add to Cart buttons */
    wrap.querySelectorAll('.foi-add-cart-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (!IS_AUTH) {
          appendMessage('bot', '🔐 Please log in to add items to your cart!');
          return;
        }
        addToCart(btn.dataset.foodId, btn);
      });
    });

    msgContainer.insertBefore(wrap, typingEl);
    scrollBottom();
  }

  /* ══════════════════════════════════════════════════════════════
     PHASE 5 — CUSTOMER FOOD RECOMMENDATIONS
  ══════════════════════════════════════════════════════════════ */
  function triggerFoodRecommendations(message) {
    setTyping(true);
    sendBtn.disabled = true;

    fetch('/ai/recommend/?q=' + encodeURIComponent(message), {
      method:  'GET',
      headers: { 'Content-Type': 'application/json' },
    })
    .then(function (r) {
      return r.json().then(function (data) { return { ok: r.ok, status: r.status, data: data }; });
    })
    .then(function (res) {
      setTyping(false);
      sendBtn.disabled = false;

      if (!res.ok) {
        appendMessage('bot', '❌ ' + (res.data.error || 'Could not fetch recommendations.'));
        return;
      }

      var data = res.data;
      if (!data.success) {
        appendMessage('bot', '❌ ' + (data.error || 'Something went wrong.'));
        return;
      }

      if (data.intro) appendMessage('bot', data.intro);
      if (data.items && data.items.length) {
        appendRecommendationCards(data.items);
      } else {
        showRoleChips();
      }
    })
    .catch(function (err) {
      setTyping(false);
      sendBtn.disabled = false;
      console.error('[FoodOnline AI] Recommendation error:', err);
      appendMessage('bot', '❌ Connection error. Please try again.');
    });
  }

  function appendRecommendationCards(items) {
    var wrap = document.createElement('div');
    wrap.className = 'foi-rec-grid';

    items.forEach(function (item) {
      var card = document.createElement('div');
      card.className = 'foi-rec-card';

      /* Image — show vendor placeholder if no image */
      var imgHtml = item.image_url
        ? '<img class="foi-rec-img" src="' + escHtml(item.image_url) + '" alt="' + escHtml(item.food_title) + '" onerror="this.style.display=\'none\';this.nextSibling.style.display=\'flex\'" />'
          + '<div class="foi-rec-img-placeholder" style="display:none">🍽️</div>'
        : '<div class="foi-rec-img-placeholder">🍽️</div>';

      card.innerHTML = [
        '<div class="foi-rec-img-wrap">' + imgHtml + '</div>',
        '<div class="foi-rec-body">',
        '  <div class="foi-rec-title">' + escHtml(item.food_title) + '</div>',
        '  <div class="foi-rec-vendor">🏪 ' + escHtml(item.vendor_name) + '</div>',
        '  <div class="foi-rec-meta">',
        '    <span class="foi-rec-category">' + escHtml(item.category) + '</span>',
        '    <span class="foi-rec-price">₹' + Number(item.price).toFixed(0) + '</span>',
        '  </div>',
        item.description
          ? '  <div class="foi-rec-desc">' + escHtml(item.description.substring(0, 80)) + (item.description.length > 80 ? '…' : '') + '</div>'
          : '',
        '  <div class="foi-rec-reason">' + escHtml(item.match_reason) + '</div>',
        '</div>',
        '<div class="foi-rec-footer foi-rec-footer--two">',
        '  <a class="foi-rec-order-btn foi-rec-btn-secondary" href="/marketplace/' + escHtml(item.vendor_slug) + '/" target="_blank">',
        '    🍽️ View Menu',
        '  </a>',
        '  <button class="foi-rec-order-btn foi-rec-btn-primary foi-add-cart-btn" data-food-id="' + item.id + '">',
        '    🛒 Add to Cart',
        '  </button>',
        '</div>',
      ].join('');

      wrap.appendChild(card);
    });

    /* Wire Add to Cart buttons */
    wrap.querySelectorAll('.foi-add-cart-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (!IS_AUTH) {
          appendMessage('bot', '🔐 Please log in to add items to your cart!');
          return;
        }
        addToCart(btn.dataset.foodId, btn);
      });
    });

    msgContainer.insertBefore(wrap, typingEl);
    scrollBottom();

    /* Post-recommendation chips */
    setTimeout(function () {
      suggsEl.innerHTML = '';
      suggsEl.style.display = 'flex';
      var chips = [
        "Something spicy 🌶️",
        "Something sweet 🍰",
        "Healthy options 🥗",
        "Show more options 🔄",
      ];
      chips.forEach(function (text) {
        var btn = document.createElement('button');
        btn.className   = 'foi-chip';
        btn.textContent = text;
        btn.addEventListener('click', function () {
          suggsEl.innerHTML = '';
          suggsEl.style.display = 'none';
          sendMessage(text);
        });
        suggsEl.appendChild(btn);
      });
    }, 500);
  }

  /* ══════════════════════════════════════════════════════════════
     PHASE 6 — NEARBY RESTAURANT DISCOVERY
  ══════════════════════════════════════════════════════════════ */
  function triggerNearbyRestaurants() {
    setTyping(true);
    sendBtn.disabled = true;

    fetch('/ai/nearby/', { method: 'GET' })
    .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
    .then(function (res) {
      setTyping(false);
      sendBtn.disabled = false;

      if (!res.ok || !res.data.success) {
        appendMessage('bot', '❌ ' + (res.data.error || 'Could not load restaurants.'));
        showRoleChips();
        return;
      }

      if (!res.data.vendors || !res.data.vendors.length) {
        appendMessage('bot', res.data.message || "No restaurants found nearby!");
        showRoleChips();
        return;
      }

      appendMessage('bot', '🗺️ Here are the restaurants available for you:');
      appendVendorCards(res.data.vendors);
      showRoleChips();
    })
    .catch(function () {
      setTyping(false);
      sendBtn.disabled = false;
      appendMessage('bot', '❌ Connection error. Please try again.');
      showRoleChips();
    });
  }

  function appendVendorCards(vendors) {
    var wrap = document.createElement('div');
    wrap.className = 'foi-vendor-grid';

    vendors.forEach(function (v) {
      var card = document.createElement('div');
      card.className = 'foi-vendor-card';

      /* Cover image — prefer cover_photo, fallback profile_picture, fallback placeholder */
      var imgHtml;
      if (v.cover_url) {
        imgHtml = '<img class="foi-vendor-cover" src="' + escHtml(v.cover_url) + '" alt="' + escHtml(v.name) + '" onerror="this.style.display=\'none\';this.nextSibling.style.display=\'flex\'" />'
                + '<div class="foi-vendor-cover-placeholder" style="display:none">🍽️</div>';
      } else if (v.profile_url) {
        imgHtml = '<img class="foi-vendor-cover" src="' + escHtml(v.profile_url) + '" alt="' + escHtml(v.name) + '" onerror="this.style.display=\'none\';this.nextSibling.style.display=\'flex\'" />'
                + '<div class="foi-vendor-cover-placeholder" style="display:none">🍽️</div>';
      } else {
        imgHtml = '<div class="foi-vendor-cover-placeholder">🍽️</div>';
      }

      /* Category tags */
      var tagsHtml = v.categories.map(function (cat) {
        return '<span class="foi-vendor-tag">' + escHtml(cat) + '</span>';
      }).join('');

      /* Distance / city badge */
      var distHtml = v.distance_str
        ? '<span class="foi-vendor-dist">📍 ' + escHtml(v.distance_str) + '</span>'
        : '';

      card.innerHTML = [
        '<div class="foi-vendor-img-wrap">' + imgHtml + '</div>',
        '<div class="foi-vendor-body">',
        '  <div class="foi-vendor-name">' + escHtml(v.name) + '</div>',
        distHtml,
        '  <div class="foi-vendor-tags">' + (tagsHtml || '<span class="foi-vendor-tag">Restaurant</span>') + '</div>',
        '</div>',
        '<div class="foi-vendor-footer foi-vendor-footer--two">',
        '  <button class="foi-vendor-info-btn" data-vendor-id="' + v.id + '">',
        '    ℹ️ Info & Hours',
        '  </button>',
        '  <a class="foi-vendor-btn" href="/marketplace/' + escHtml(v.slug) + '/" target="_blank">',
        '    🛒 View Menu',
        '  </a>',
        '</div>',
      ].join('');

      /* Wire Info button */
      card.querySelector('.foi-vendor-info-btn').addEventListener('click', function () {
        triggerVendorInfo(v.id, v.name, card);
      });

      wrap.appendChild(card);
    });

    msgContainer.insertBefore(wrap, typingEl);
    scrollBottom();
  }
  init();

}());