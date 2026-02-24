# apps/inventory/urls.py

from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Dashboard
    path('', views.inventory_dashboard, name='inv_dashboard'),

    # Stock Adjustment
    path('adjust/', views.adjust_stock, name='adjust_stock'),

    # Variant Stock Detail
    path('variant/<int:pk>/', views.variant_stock_detail, name='variant_detail'),

    # Movement Log
    path('movements/', views.movement_log, name='movement_log'),
]