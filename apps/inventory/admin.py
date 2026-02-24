# apps/inventory/admin.py
"""
Admin interface for inventory management
"""
from django.contrib import admin
from .models import StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    """Admin for stock movements"""

    list_display = [
        'variant',
        'movement_type',
        'quantity',
        'stock_after',
        'reason',
        'user',
        'created_at'
    ]

    list_filter = [
        'movement_type',
        'reason',
        'created_at'
    ]

    search_fields = [
        'variant__sku',
        'variant__product__name',
        'notes'
    ]

    readonly_fields = [
        'variant',
        'movement_type',
        'quantity',
        'stock_before',
        'stock_after',
        'reason',
        'notes',
        'user',
        'created_at'
    ]

    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        """Prevent adding movements directly in admin"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deleting movements (audit log)"""
        return False