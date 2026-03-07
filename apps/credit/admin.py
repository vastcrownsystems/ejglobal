# apps/credit/admin.py - FIX customer_link method

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import CreditLedger, CreditPayment


@admin.register(CreditLedger)
class CreditLedgerAdmin(admin.ModelAdmin):
    list_display = [
        'ledger_id',
        'customer_link',  # ✅ This is the problematic method
        'order_link',
        'transaction_type',
        'total_amount',
        'amount_paid',
        'balance_outstanding',
        'status',
        'due_date',
        'is_overdue_badge',
        'transaction_date',
    ]

    list_filter = [
        'status',
        'transaction_type',
        'transaction_date',
        'due_date',
    ]

    search_fields = [
        'ledger_id',
        'customer__full_name',
        'customer__customer_number',
        'order__order_number',
    ]

    readonly_fields = [
        'ledger_id',
        'balance_outstanding',
        'created_at',
        'updated_at',
    ]

    date_hierarchy = 'transaction_date'

    def customer_link(self, obj):
        """Link to customer detail page"""
        if obj.customer:
            # ✅ FIX: Use the correct URL pattern
            # Try customer app URL first, fall back to admin if needed
            try:
                # Use your custom customer detail view
                url = reverse('customers:customer_detail', args=[obj.customer.pk])
                return format_html(
                    '<a href="{}" target="_blank">{}</a>',
                    url,
                    obj.customer.full_name
                )
            except:
                # Fallback: Try admin URL with correct pattern
                try:
                    # The correct pattern is: appname_modelname_change
                    url = reverse('admin:customers_customer_change', args=[obj.customer.pk])
                    return format_html(
                        '<a href="{}">{}</a>',
                        url,
                        obj.customer.full_name
                    )
                except:
                    # If all else fails, just return the name
                    return obj.customer.full_name
        return "-"

    customer_link.short_description = 'Customer'

    def order_link(self, obj):
        """Link to order detail page"""
        if obj.order:
            try:
                # Use your custom order detail view
                url = reverse('orders:order_detail', args=[obj.order.pk])
                return format_html(
                    '<a href="{}" target="_blank">{}</a>',
                    url,
                    obj.order.order_number
                )
            except:
                # Fallback to admin
                try:
                    url = reverse('admin:orders_order_change', args=[obj.order.pk])
                    return format_html(
                        '<a href="{}">{}</a>',
                        url,
                        obj.order.order_number
                    )
                except:
                    return obj.order.order_number
        return "-"

    order_link.short_description = 'Order'

    def is_overdue_badge(self, obj):
        """Display overdue status as badge"""
        if obj.is_overdue:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">'
                'OVERDUE ({} days)'
                '</span>',
                obj.days_overdue
            )
        elif obj.days_until_due is not None and obj.days_until_due <= 7:
            return format_html(
                '<span style="background-color: #ffc107; color: black; padding: 3px 10px; border-radius: 3px; font-weight: bold;">'
                'Due in {} days'
                '</span>',
                obj.days_until_due
            )
        # ✅ FIX: format_html needs at least one placeholder
        return format_html(
            '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">'
            '{}'
            '</span>',
            'Current'  # ✅ Pass 'Current' as an argument
        )

    is_overdue_badge.short_description = 'Status'


@admin.register(CreditPayment)
class CreditPaymentAdmin(admin.ModelAdmin):
    list_display = [
        'payment_id',
        'customer_link',
        'ledger_link',
        'amount',
        'payment_method',
        'payment_date',
        'received_by',
    ]

    list_filter = [
        'payment_method',
        'payment_date',
    ]

    search_fields = [
        'payment_id',
        'customer__full_name',
        'ledger__ledger_id',
        'reference_number',
    ]

    readonly_fields = [
        'payment_id',
        'created_at',
    ]

    date_hierarchy = 'payment_date'

    def customer_link(self, obj):
        """Link to customer"""
        if obj.customer:
            try:
                url = reverse('customers:customer_detail', args=[obj.customer.pk])
                return format_html(
                    '<a href="{}" target="_blank">{}</a>',
                    url,
                    obj.customer.full_name
                )
            except:
                return obj.customer.full_name
        return "-"

    customer_link.short_description = 'Customer'

    def ledger_link(self, obj):
        """Link to ledger entry"""
        if obj.ledger:
            try:
                url = reverse('admin:credit_creditledger_change', args=[obj.ledger.pk])
                return format_html(
                    '<a href="{}">{}</a>',
                    url,
                    obj.ledger.ledger_id
                )
            except:
                return obj.ledger.ledger_id
        return "-"

    ledger_link.short_description = 'Ledger'

# ═══════════════════════════════════════════════════════════════════
# ALTERNATIVE SIMPLER VERSION (if the above still has issues)
# ═══════════════════════════════════════════════════════════════════

# @admin.register(CreditLedger)
# class CreditLedgerAdmin(admin.ModelAdmin):
#     list_display = [
#         'ledger_id',
#         'get_customer_name',  # ✅ Just show name, no link
#         'get_order_number',   # ✅ Just show order number, no link
#         'transaction_type',
#         'total_amount',
#         'amount_paid',
#         'balance_outstanding',
#         'status',
#         'due_date',
#         'transaction_date',
#     ]
#
#     list_filter = [
#         'status',
#         'transaction_type',
#         'transaction_date',
#     ]
#
#     search_fields = [
#         'ledger_id',
#         'customer__full_name',
#         'order__order_number',
#     ]
#
#     readonly_fields = [
#         'ledger_id',
#         'balance_outstanding',
#     ]
#
#     def get_customer_name(self, obj):
#         return obj.customer.full_name if obj.customer else "-"
#     get_customer_name.short_description = 'Customer'
#
#     def get_order_number(self, obj):
#         return obj.order.order_number if obj.order else "-"
#     get_order_number.short_description = 'Order'