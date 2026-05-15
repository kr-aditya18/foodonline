from django.urls import path
from . import views

urlpatterns = [
    # ── Phase 1 
    path('chat/',           views.chat_api,          name='ai_chat'),
    path('clear-session/',  views.clear_session,     name='ai_clear_session'),
    path('history/',        views.get_history,        name='ai_history'),
    path('status/',         views.assistant_status,  name='ai_status'),

    # ── Phase 2 
    path('generate-food-item/', views.generate_food_item_view, name='ai_generate_food_item'),
    path('save-food-item/',     views.save_food_item_view,     name='ai_save_food_item'),
]