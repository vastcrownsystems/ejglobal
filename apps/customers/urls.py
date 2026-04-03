# apps/customers/urls.py - Complete Customer URLs

from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    # Dashboard
    path('', views.customer_dashboard, name='customer_dashboard'),

    # List & Search
    path('list/', views.customer_list, name='customer_list'),

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

    # Credit Management (Admin/Manager Only)
    path('<int:pk>/update-credit-status/', views.update_credit_status, name='update_credit_status'),
    path('credit-report/', views.credit_customers_report, name='credit_customers_report'),

    # ── Sales Persons ───
    path('sales-persons/', views.salesperson_list, name='salesperson_list'),
    path('sales-persons/create/', views.salesperson_create, name='salesperson_create'),
    path('sales-persons/search/', views.salesperson_search_api, name='salesperson_search_api'),
    path('sales-persons/<int:pk>/', views.salesperson_detail, name='salesperson_detail'),
    path('sales-persons/<int:pk>/edit/', views.salesperson_edit, name='salesperson_edit'),
    path('sales-persons/<int:pk>/delete/', views.salesperson_delete, name='salesperson_delete'),
    path('sales-persons/<int:pk>/reassign/', views.salesperson_reassign_customers, name='salesperson_reassign'),
]