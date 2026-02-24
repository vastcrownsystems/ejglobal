# apps/catalog/urls.py

from django.urls import path
from . import views

app_name = 'catalog'

urlpatterns = [
    # Product URLs
    path('products/', views.product_list, name='product_list'),
    path('products/create/', views.product_create, name='product_create'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('products/<int:pk>/toggle/', views.product_toggle_status, name='product_toggle_status'),

    # Variant URLs
    path('variants/', views.variant_list, name='variant_list'),
    path('variants/create/', views.variant_create, name='variant_create'),
    path('variants/<int:pk>/', views.variant_detail, name='variant_detail'),
    path('variants/<int:pk>/edit/', views.variant_edit, name='variant_edit'),
    path('variants/<int:pk>/delete/', views.variant_delete, name='variant_delete'),
    path('variants/<int:pk>/toggle/', views.variant_toggle_status, name='variant_toggle_status'),
    path('variants/<int:pk>/adjust-stock/', views.variant_adjust_stock, name='variant_adjust_stock'),


    # Variant Attribute URLs
    path('attributes/', views.attribute_list, name='attribute_list'),
    path('attributes/create/', views.attribute_create, name='attribute_create'),
    path('attributes/<int:pk>/', views.attribute_detail, name='attribute_detail'),
    path('attributes/<int:pk>/edit/', views.attribute_edit, name='attribute_edit'),
    path('attributes/<int:pk>/delete/', views.attribute_delete, name='attribute_delete'),
    path('attributes/<int:attribute_pk>/bulk-values/', views.attribute_bulk_values, name='attribute_bulk_values'),

    # Attribute Value URLs
    path('attribute-values/create/', views.attribute_value_create, name='attribute_value_create'),
    path('attribute-values/create/<int:attribute_pk>/', views.attribute_value_create,
         name='attribute_value_create_for'),
    path('attribute-values/<int:pk>/edit/', views.attribute_value_edit, name='attribute_value_edit'),
    path('attribute-values/<int:pk>/delete/', views.attribute_value_delete, name='attribute_value_delete'),
]