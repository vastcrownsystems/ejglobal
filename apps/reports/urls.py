# apps/reports/urls.py - Complete Reports URLs

from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # ============================================
    # MAIN DASHBOARD
    # ============================================
    path('', views.reports_dashboard, name='reports_dashboard'),

    # ============================================
    # STANDARD REPORTS
    # ============================================
    path('daily/', views.daily_report_view, name='daily_report'),
    path('weekly/', views.weekly_report_view, name='weekly_report'),
    path('monthly/', views.monthly_report_view, name='monthly_report'),
    path('yearly/', views.yearly_report_view, name='yearly_report'),
    path('custom/', views.custom_report_view, name='custom_report'),

    # ============================================
    # PRODUCT REPORTS
    # ============================================
    path('product/<int:product_id>/', views.product_performance_report, name='product_performance'),
    path('products/top/', views.top_products_report, name='top_products'),
    path('categories/', views.category_report, name='category_report'),

    # ============================================
    # API ENDPOINTS (for charts/AJAX)
    # ============================================
    path('api/sales-chart/', views.sales_chart_data, name='sales_chart_data'),
    path('api/quick-stats/', views.quick_stats_api, name='quick_stats_api'),

    # ============================================
    # EXPORTS
    # ============================================
    path('export/pdf/<str:report_type>/<int:report_id>/', views.export_report_pdf, name='export_pdf'),
    path('export/excel/<str:report_type>/<int:report_id>/', views.export_report_excel, name='export_excel'),
    path('export/custom/', views.export_custom_report, name='export_custom'),
]