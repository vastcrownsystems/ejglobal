# apps/sales/urls.py

from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('', views.session_dashboard, name='session_dashboard'),
    path('start/', views.start_session, name='start_session'),
    path('close/<int:session_id>/', views.close_session, name='close_session'),
    path('session/<int:session_id>/', views.session_detail, name='session_detail'),

    # Stores
    path('stores/', views.store_list, name='store_list'),
    path('stores/create/', views.store_create, name='store_create'),
    path('stores/<int:pk>/', views.store_detail, name='store_detail'),
    path('stores/<int:pk>/edit/', views.store_edit, name='store_edit'),

    # Registers
    path('registers/', views.register_list, name='register_list'),
    path('registers/create/', views.register_create, name='register_create'),
    path('registers/<int:pk>/', views.register_detail, name='register_detail'),
    path('registers/<int:pk>/edit/', views.register_edit, name='register_edit'),
]