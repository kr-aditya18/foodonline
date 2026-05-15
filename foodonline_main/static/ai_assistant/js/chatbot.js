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
 */

(function () {
  'use strict';

  /* ── CSRF helper (same pattern as your existing Django AJAX) ── */
  function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      var cookies = document.cookie.split(';');
      for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  /* ── Read config from #foi-config data attributes ── */
  var cfg = document.getElementById('foi-config');
  if (!cfg) return;

  var CHAT_API_URL    = cfg.dataset.chatUrl;
  var CLEAR_API_URL   = cfg.dataset.clearUrl;
  var HISTORY_API_URL = cfg.dataset.historyUrl;
  var STATUS_API_URL  = cfg.dataset.statusUrl;
  var IS_AUTH         = cfg.dataset.authenticated === 'true';
  var INITIAL_ROLE    = cfg.dataset.role || 'guest';

  /* ── State ── */
  var sessionKey    = localStorage.getItem('foi_session_key') || '';
  var isOpen        = false;
  var isTyping      = false;
  var currentRole   = INITIAL_ROLE;
  var recognition   = null;
  var isListening   = false;
  var preferredVoice = null;  // ← declared ONCE here

  /* ── DOM refs ── */
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

  /* ── Verify critical DOM elements exist ── */
  if (!fab || !chatWin || !msgContainer || !typingEl || !inputEl) {
    console.warn('FoodOnline AI: Required DOM elements missing. Check chatbot_widget.html.');
    return;
  }

  if (typingEl.parentElement !== msgContainer) {
    console.warn('FoodOnline AI: #foi-typing must be a direct child of #foi-messages.');
    return;
  }

  /* ── Role config ── */
  var ROLE_CONFIG = {
    vendor: {
      label:   'Vendor',
      welcome: "👋 Hi! I'm your AI menu assistant. Describe any dish and I'll generate the perfect title, description, price, and tags. What would you like to add today?",
      chips:   ['Generate a food item 🍱', 'Compare my pricing 💰', 'Suggest categories 📋', 'Menu improvement tips ✨'],
    },
    customer: {
      label:   'Customer',
      welcome: "🍕 Hey there, foodie! Tell me what you're craving or how you're feeling and I'll find the perfect meal for you. What sounds good today?",
      chips:   ["I'm feeling spicy 🌶️", "Something healthy 🥗", "Comfort food 🍜", "Best near me 📍"],
    },
    guest: {
      label:   'Guest',
      welcome: "👋 Welcome to FoodOnline! I can help you discover restaurants and answer your questions. Log in for personalised recommendations!",
      chips:   ['How does FoodOnline work? 🤔', 'Find restaurants 🗺️', 'Register as a vendor 🏪', 'Login to my account 🔐'],
    },
  };

  /* ════════════════════════════════════════════════════════════
     VOICE SETUP  (declared early so speakReply can use it)
  ════════════════════════════════════════════════════════════ */

  function loadBestVoice() {
    if (!window.speechSynthesis) return;
    var voices = window.speechSynthesis.getVoices();
    if (!voices.length) return;

    var preferred = [
      'Google UK English Female',
      'Google US English',
      'Microsoft Aria Online (Natural) - English (United States)',
      'Microsoft Jenny Online (Natural) - English (United States)',
      'Samantha',   // macOS/iOS
      'Karen',      // macOS
      'Daniel',     // macOS UK
    ];

    for (var i = 0; i < preferred.length; i++) {
      var found = voices.find(function (v) { return v.name === preferred[i]; });
      if (found) { preferredVoice = found; return; }
    }

    // Fallback: any online English voice, then any English voice
    preferredVoice = voices.find(function (v) {
      return v.lang.startsWith('en') && v.localService === false;
    }) || voices.find(function (v) {
      return v.lang.startsWith('en');
    }) || null;
  }

  if (window.speechSynthesis) {
    window.speechSynthesis.onvoiceschanged = loadBestVoice;
    loadBestVoice();
  }

  /* ════════════════════════════════════════════════════════════
     INIT
  ════════════════════════════════════════════════════════════ */
  function init() {
    renderRoleBadge(currentRole);
    showWelcome(currentRole);
    renderChips(currentRole);
    bindEvents();
    fetchStatus();
    restoreHistory();

    setTimeout(function () {
      if (!isOpen) fabDot.style.display = 'block';
    }, 3000);
  }

  /* ── Ping status endpoint to confirm role from server ── */
  function fetchStatus() {
    fetch(STATUS_API_URL)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.role && data.role !== currentRole) {
          currentRole = data.role;
          renderRoleBadge(currentRole);
          renderChips(currentRole);
          var hasMessages = msgContainer.querySelectorAll('.foi-msg:not(#foi-typing)').length === 0;
          if (hasMessages) showWelcome(currentRole);
        }
      })
      .catch(function () {});
  }

  function renderRoleBadge(role) {
    var rc = ROLE_CONFIG[role] || ROLE_CONFIG.guest;
    roleLabel.textContent = rc.label;
  }

  function showWelcome(role) {
    var rc = ROLE_CONFIG[role] || ROLE_CONFIG.guest;
    appendMessage('bot', rc.welcome);
  }

  function renderChips(role) {
    var rc = ROLE_CONFIG[role] || ROLE_CONFIG.guest;
    suggsEl.innerHTML = '';
    rc.chips.forEach(function (text) {
      var btn = document.createElement('button');
      btn.className   = 'foi-chip';
      btn.textContent = text;
      btn.addEventListener('click', function () { sendMessage(text); });
      suggsEl.appendChild(btn);
    });
  }

  /* ════════════════════════════════════════════════════════════
     EVENT BINDING
  ════════════════════════════════════════════════════════════ */
  function bindEvents() {
    fab.addEventListener('click', toggleChat);
    closeBtn.addEventListener('click', closeChat);
    clearBtn.addEventListener('click', clearChat);
    sendBtn.addEventListener('click', function () { sendMessage(); });
    voiceBtn.addEventListener('click', toggleVoice);

    inputEl.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    inputEl.addEventListener('input', autoResize);

    document.addEventListener('click', function (e) {
      if (isOpen && !chatWin.contains(e.target) && e.target !== fab) closeChat();
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && isOpen) closeChat();
    });
  }

  /* ════════════════════════════════════════════════════════════
     OPEN / CLOSE
  ════════════════════════════════════════════════════════════ */
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

  /* ════════════════════════════════════════════════════════════
     SEND MESSAGE
  ════════════════════════════════════════════════════════════ */
  function sendMessage(overrideText) {
    var text = (overrideText !== undefined ? overrideText : inputEl.value).trim();
    if (!text || isTyping) return;

    appendMessage('user', text);
    inputEl.value         = '';
    inputEl.style.height  = 'auto';
    setTyping(true);
    sendBtn.disabled      = true;
    suggsEl.style.display = 'none';

    fetch(CHAT_API_URL, {
      method:  'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken':  getCookie('csrftoken'),
      },
      body: JSON.stringify({ message: text, session_key: sessionKey }),
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

  /* ════════════════════════════════════════════════════════════
     MESSAGE RENDERING
  ════════════════════════════════════════════════════════════ */
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
    isTyping               = show;
    typingEl.style.display = show ? 'flex' : 'none';
    if (show) scrollBottom();
  }

  function scrollBottom() {
    requestAnimationFrame(function () {
      msgContainer.scrollTop = msgContainer.scrollHeight;
    });
  }

  function autoResize() {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 90) + 'px';
  }

  function formatTime(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  /* ════════════════════════════════════════════════════════════
     CLEAR CHAT
  ════════════════════════════════════════════════════════════ */
  function clearChat() {
    if (!confirm('Start a new conversation?')) return;

    if (sessionKey) {
      fetch(CLEAR_API_URL, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        body: JSON.stringify({ session_key: sessionKey }),
      }).catch(function () {});
    }

    sessionKey = '';
    localStorage.removeItem('foi_session_key');

    var children = Array.prototype.slice.call(msgContainer.children);
    children.forEach(function (child) {
      if (child.id !== 'foi-typing') msgContainer.removeChild(child);
    });
    typingEl.style.display = 'none';
    suggsEl.style.display  = 'flex';
    showWelcome(currentRole);
    renderChips(currentRole);
  }

  /* ════════════════════════════════════════════════════════════
     RESTORE HISTORY
  ════════════════════════════════════════════════════════════ */
  function restoreHistory() {
    if (!IS_AUTH || !sessionKey) return;

    fetch(HISTORY_API_URL + '?session_key=' + encodeURIComponent(sessionKey))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success && data.messages && data.messages.length > 1) {
          var children = Array.prototype.slice.call(msgContainer.children);
          children.forEach(function (child) {
            if (child.id !== 'foi-typing') msgContainer.removeChild(child);
          });
          data.messages.forEach(function (m) { appendMessage(m.role, m.content); });
          suggsEl.style.display = 'none';
        }
      })
      .catch(function () {});
  }

  /* ════════════════════════════════════════════════════════════
     VOICE INPUT  (Web Speech API)
  ════════════════════════════════════════════════════════════ */
  function toggleVoice() {
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SR) {
      appendMessage('bot', "🎤 Voice input isn't supported in your browser. Try Chrome or Edge!");
      return;
    }

    if (isListening) {
      if (recognition) recognition.stop();
      return;
    }

    recognition                 = new SR();
    recognition.lang            = 'en-IN';
    recognition.interimResults  = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = function () {
      isListening = true;
      voiceBtn.classList.add('foi-listening');
      inputEl.placeholder = '🎤 Listening…';
    };

    recognition.onresult = function (event) {
      inputEl.value = event.results[0][0].transcript;
      autoResize();
    };

    recognition.onerror = function (event) {
      console.warn('Speech error:', event.error);
    };

    recognition.onend = function () {
      isListening = false;
      voiceBtn.classList.remove('foi-listening');
      inputEl.placeholder = 'Ask me anything about food…';
    };

    recognition.start();
  }

  /* ════════════════════════════════════════════════════════════
     VOICE OUTPUT  (Web Speech Synthesis — improved quality)
  ════════════════════════════════════════════════════════════ */
  function speakReply(text) {
    if (!window.speechSynthesis || !text) return;

    var cleanText = text
      .replace(/\*\*(.*?)\*\*/g, '$1')
      .replace(/\*(.*?)\*/g, '$1')
      .replace(/#+\s/g, '')
      .replace(/[₹$€]/g, ' rupees ')
      .trim();

    if (cleanText.length > 250) cleanText = cleanText.substring(0, 250) + '…';

    window.speechSynthesis.cancel();

    var u = new SpeechSynthesisUtterance(cleanText);
    if (preferredVoice) u.voice = preferredVoice;
    u.lang   = 'en-US';
    u.rate   = 0.95;
    u.pitch  = 1.05;
    u.volume = 0.9;
    window.speechSynthesis.speak(u);
  }

  /* ── Start ── */
  init();

}());