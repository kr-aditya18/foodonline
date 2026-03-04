from django.urls import path,include
from accounts import views as AccountViews
from . import views
urlpatterns = [
    path('',AccountViews.vendordashboard,name='vendor'),
    path('profile/',views.vprofile,name='vprofile'),
    
]
