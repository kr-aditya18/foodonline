# FILE LOCATION: ai_assistant/context_processors.py
#
# RULES — context processors run on EVERY request during template rendering.
# Violating any rule below causes RecursionError:
#
#   ✗ Never call render() / loader.get_template() / TemplateResponse here
#   ✗ Never raise unhandled exceptions (Django renders an error page,
#     which calls this processor again → infinite recursion)
#   ✗ Never import at module level anything that touches Django's template
#     machinery or triggers AppRegistry before it's ready
#   ✓ Keep it fast — one tiny function, no DB hits, lazy imports only


def ai_assistant_context(request):
    """
    Injects ``user_role`` ('vendor' | 'customer' | 'guest') into
    every template context automatically.

    Completely safe: no DB query, no template call, no heavy import.
    The get_user_role import is inside the function so it never runs
    at module load time (avoids AppRegistry-not-ready errors on startup).
    """
    try:
        # Lazy import — only runs when a request comes in, never at startup
        from .utils import get_user_role
        role = get_user_role(request.user)
    except Exception:
        # If anything goes wrong (e.g. DB not ready, migration pending),
        # silently fall back to 'guest' so the page still renders.
        role = 'guest'

    return {
        'user_role': role,
    }