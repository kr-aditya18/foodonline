from django.urls import path
from . import views

urlpatterns = [
    path('chat/',                views.chat_api,                name='ai_chat'),
    path('clear-session/',       views.clear_session,           name='ai_clear_session'),
    path('history/',             views.get_history,             name='ai_history'),
    path('status/',              views.assistant_status,        name='ai_status'),
    path('generate-food-item/',  views.generate_food_item_view, name='ai_generate_food_item'),
    path('save-food-item/',      views.save_food_item_view,     name='ai_save_food_item'),
    path('compare-pricing/',     views.compare_pricing_view,    name='ai_compare_pricing'),
    path('recommend/',           views.recommend_food_view,     name='ai_recommend'),
    path('orders/',              views.order_tracking_view,     name='ai_orders'),
    path('reorder/',             views.reorder_suggestions_view, name='ai_reorder'),
    path('nearby/',              views.nearby_restaurants_view,  name='ai_nearby'),
    path('vendor-info/<int:vendor_id>/', views.vendor_info_view, name='ai_vendor_info'),
    path('nudge/',                       views.proactive_nudge_view,        name='ai_nudge'),
    path('reviews/pending/',             views.pending_reviews_view,        name='ai_reviews_pending'),
    path('reviews/submit/',              views.submit_review_view,          name='ai_review_submit'),
    path('reviews/dismiss/',             views.dismiss_reminder_view,       name='ai_review_dismiss'),
    path('reviews/food/<int:food_id>/',  views.food_reviews_view,           name='ai_food_reviews'),
    path('recommend/by-ratings/',        views.recommend_by_ratings_view,   name='ai_recommend_by_ratings'),
    path('onboarding/status/',           views.onboarding_status_view,      name='ai_onboarding_status'),
    path('onboarding/complete/',         views.onboarding_complete_view,    name='ai_onboarding_complete'),
]