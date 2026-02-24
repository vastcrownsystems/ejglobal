# apps/reports/urls.py
from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Dashboard
    path('', views.reports_dashboard, name='reports_dashboard'),

    # Report Views (auto-generate if missing)
    path('daily/', views.daily_report_view, name='daily_report'),
    path('weekly/', views.weekly_report_view, name='weekly_report'),
    path('monthly/', views.monthly_report_view, name='monthly_report'),
    path('yearly/', views.yearly_report_view, name='yearly_report'),
    path('custom/', views.custom_report_view, name='custom_report'),

    # Export
    path('export/pdf/<str:report_type>/<int:report_id>/', views.export_report_pdf, name='export_pdf'),
    path('export/excel/<str:report_type>/<int:report_id>/', views.export_report_excel, name='export_excel'),
]