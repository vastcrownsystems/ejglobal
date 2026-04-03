# apps/reports/urls.py

from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    path("",                        views.reports_dashboard,             name="dashboard"),
    path("history/",                views.report_history,                name="history"),
    path("generate/<str:report_type>/", views.generate_report,           name="generate_report"),
    path("download/<int:pk>/",      views.download_report,               name="download_report"),
    path("api/quick/",              views.quick_reports_api,             name="quick_reports_api"),

    # ── Comprehensive report ──
    path("comprehensive/",          views.comprehensive_report_page,     name="comprehensive_report"),
    path("comprehensive/download/", views.comprehensive_report_download, name="comprehensive_report_download"),
]