from django.urls import path
from .views import index, dashboard

urlpatterns = [
    path('', dashboard, name='dashboard'),
]