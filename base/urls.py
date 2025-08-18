from django.contrib import admin
from django.urls import path, include
from base.views import gate_to_home_or_login
from . import views

urlpatterns = [
    path("", gate_to_home_or_login, name="root"),
    path("", views.home, name="home"),
    path("accounts/", include("accounts.urls")),    
]
