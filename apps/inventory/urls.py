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

    # Approval Workflow
    path('pending/', views.pending_adjustments, name='pending_adjustments'),
    path('adjustment/<int:pk>/', views.adjustment_detail, name='adjustment_detail'),
    path('adjustment/<int:pk>/approve/', views.approve_adjustment, name='approve_adjustment'),
    path('adjustment/<int:pk>/reject/', views.reject_adjustment, name='reject_adjustment'),
]