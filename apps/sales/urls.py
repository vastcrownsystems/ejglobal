# apps/sales/urls.py

from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('', views.session_dashboard, name='session_dashboard'),
    path('start/', views.start_session, name='start_session'),
    path('close/<int:session_id>/', views.close_session, name='close_session'),
    path('session/<int:session_id>/', views.session_detail, name='session_detail'),
]