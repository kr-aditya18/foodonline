import json
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import ChatSession, ChatMessage, GuestChatLog
from .utils import (
    get_user_role,
    generate_session_key,
    call_openrouter,
    build_message_history,
    get_client_ip,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# MAIN CHAT ENDPOINT
# ──────────────────────────────────────────────────────────────

@require_POST
def chat_api(request):
    """
    AJAX endpoint — receives a user message, calls OpenRouter,
    returns AI reply.

    POST JSON body:
        message     : str   — the user's message
        session_key : str   — optional, to continue a session

    Response JSON:
        success     : bool
        reply       : str
        session_key : str
        role        : str
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    user_message = body.get('message', '').strip()
    client_key   = body.get('session_key', '')

    if not user_message:
        return JsonResponse({'success': False, 'error': 'Message cannot be empty'}, status=400)

    if len(user_message) > 1000:
        return JsonResponse({'success': False, 'error': 'Message too long (max 1000 chars)'}, status=400)

    user = request.user
    role = get_user_role(user)

    # ── Authenticated user ──────────────────────────────────
    if user.is_authenticated:
        session = _get_or_create_session(user, role, client_key)

        # Persist user message
        ChatMessage.objects.create(session=session, role='user', content=user_message)

        # Call AI with full history
        history = build_message_history(session)
        result  = call_openrouter(history, role=role)
        ai_reply = result['reply']

        # Persist AI reply
        ChatMessage.objects.create(session=session, role='assistant', content=ai_reply)

        return JsonResponse({
            'success':     True,
            'reply':       ai_reply,
            'session_key': session.session_key,
            'role':        role,
        })

    # ── Guest user (no DB session) ──────────────────────────
    result   = call_openrouter([{"role": "user", "content": user_message}], role='guest')
    ai_reply = result['reply']
    guest_key = client_key or generate_session_key()

    try:
        GuestChatLog.objects.create(
            session_key     = guest_key,
            user_message    = user_message[:500],
            assistant_reply = ai_reply[:500],
            ip_address      = get_client_ip(request),
        )
    except Exception as e:
        logger.warning(f"Guest log failed: {e}")

    return JsonResponse({
        'success':     True,
        'reply':       ai_reply,
        'session_key': guest_key,
        'role':        'guest',
    })


# ──────────────────────────────────────────────────────────────
# CLEAR SESSION
# ──────────────────────────────────────────────────────────────

@require_POST
def clear_session(request):
    """Mark a session inactive so the user starts fresh."""
    if not request.user.is_authenticated:
        return JsonResponse({'success': True})

    try:
        body = json.loads(request.body)
        key  = body.get('session_key', '')
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    if key:
        ChatSession.objects.filter(session_key=key, user=request.user).update(is_active=False)

    return JsonResponse({'success': True})


# ──────────────────────────────────────────────────────────────
# GET HISTORY  (restores chat on page reload)
# ──────────────────────────────────────────────────────────────

def get_history(request):
    """Return last 20 messages for a session (GET request)."""
    if not request.user.is_authenticated:
        return JsonResponse({'success': True, 'messages': []})

    key = request.GET.get('session_key', '')
    if not key:
        return JsonResponse({'success': True, 'messages': []})

    try:
        session  = ChatSession.objects.get(session_key=key, user=request.user, is_active=True)
        messages = session.messages.filter(role__in=['user', 'assistant']).order_by('created_at')[:20]
        data     = [{'role': m.role, 'content': m.content} for m in messages]
        return JsonResponse({'success': True, 'messages': data})
    except ChatSession.DoesNotExist:
        return JsonResponse({'success': True, 'messages': []})


# ──────────────────────────────────────────────────────────────
# STATUS / HEALTH
# ──────────────────────────────────────────────────────────────

def assistant_status(request):
    """Frontend pings this to confirm assistant is online and get role."""
    return JsonResponse({
        'online':        True,
        'role':          get_user_role(request.user),
        'authenticated': request.user.is_authenticated,
    })


# ──────────────────────────────────────────────────────────────
# PRIVATE HELPERS
# ──────────────────────────────────────────────────────────────

def _get_or_create_session(user, role, session_key=''):
    """Return existing active session or create a new one."""
    if session_key:
        try:
            return ChatSession.objects.get(session_key=session_key, user=user, is_active=True)
        except ChatSession.DoesNotExist:
            pass
    return ChatSession.objects.create(
        user=user,
        mode=role,
        session_key=generate_session_key(),
    )