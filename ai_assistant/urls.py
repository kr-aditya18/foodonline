# FILE LOCATION: ai_assistant/urls.py
#
# app_name here is the ONLY place the namespace should be declared.
# The include() in foodonline_main/urls.py must NOT also pass namespace=.
# Declaring it in both places = RecursionError.

from django.urls import path
from . import views

app_name = 'ai_assistant'

urlpatterns = [
    path('chat/', views.chat_api,name='chat_api'),
    path('clear-session/', views.clear_session,name='clear_session'),
    path('history/',views.get_history,name='history'),
    path('status/', views.assistant_status, name='status'),
]
