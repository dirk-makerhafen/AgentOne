from django.urls import path
from . import views

urlpatterns = [
    path('register_client/', views.register_client, name='register_client'),
]
