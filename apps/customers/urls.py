# apps/customers/urls.py - Complete Customer URLs

from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.customer_dashboard, name='customer_dashboard'),

    # List & Search
    path('', views.customer_list, name='customer_list'),

    # CRUD Operations
    path('create/', views.customer_create, name='customer_create'),
    path('<int:pk>/', views.customer_detail, name='customer_detail'),
    path('<int:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('<int:pk>/delete/', views.customer_delete, name='customer_delete'),

    # POS Integration (Modal & Search)
    path('modal/', views.customer_search_modal, name='customer_search_modal'),
    path('search/', views.customer_search, name='customer_search'),

    # POS Actions
    path('quick-add/', views.quick_add_customer, name='quick_add'),
    path('select/', views.select_customer, name='select_customer'),
    path('skip/', views.skip_customer, name='skip_customer'),

    path('<int:pk>/refresh-stats/', views.refresh_customer_stats, name='refresh_stats'),
]