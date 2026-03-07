# apps/credit/urls.py
"""
Credit Ledger URL Configuration
"""
from django.urls import path
from . import views

app_name = 'credit'

urlpatterns = [
    # Customer Credit Management
    path('customer/<int:customer_id>/', views.customer_credit_dashboard, name='customer_dashboard'),
    path('customer/<int:customer_id>/statement/', views.customer_statement, name='customer_statement'),

    # Ledger Management
    path('ledger/', views.credit_ledger_list,  name='ledger_list'),
    path('ledger/<str:ledger_id>/', views.ledger_detail, name='ledger_detail'),
    path('ledger/<str:ledger_id>/pay/', views.record_credit_payment, name='record_payment'),

    # Reports
    path('reports/aging/',views.aging_report, name='aging_report' ),
    path('reports/outstanding/', views.outstanding_balance_report, name='outstanding_report'),
    path('reports/collections/', views.collection_report, name='collection_report'),

    # Customer Lists
    path('customers/', views.credit_customers_list, name='customers_list'),
]