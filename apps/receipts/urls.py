# apps/receipts/urls.py - Receipt URLs

from django.urls import path
from . import views

app_name = 'receipts'

urlpatterns = [
    # Receipt list
    path('', views.receipt_list, name='receipt_list'),

    # Receipt detail (full page)
    path('<int:pk>/', views.receipt_detail, name='receipt_detail'),

    # Receipt modal (for printing)
    path('<int:pk>/modal/', views.receipt_modal, name='receipt_modal'),

    # Print view (80mm thermal)
    path('<int:pk>/print/', views.receipt_print, name='receipt_print'),

    # Increment print count
    path('<int:pk>/print-count/', views.increment_print_count, name='increment_print_count'),

    # Download PDF
    path('<int:pk>/download/', views.download_pdf, name='download_pdf'),
]