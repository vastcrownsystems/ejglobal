# apps/reports/urls.py - Complete Reports URLs

from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Dashboard
    path('', views.reports_dashboard, name='dashboard'),

    # Generate reports
    path('generate/<str:report_type>/', views.generate_report, name='generate_report'),

    # Download reports
    path('download/<int:pk>/', views.download_report, name='download_report'),

    # History
    path('history/', views.report_history, name='history'),

    # API endpoints
    path('api/quick/', views.quick_reports_api, name='quick_api'),
]