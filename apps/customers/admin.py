# apps/customers/admin.py - ADD/UPDATE Customer Admin

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Q
from .models import Customer, CustomerNote


class CustomerNoteInline(admin.TabularInline):
    model = CustomerNote
    extra = 0
    fields = ['note_type', 'note', 'created_by', 'created_at']
    readonly_fields = ['created_at']


class CreditLedgerInline(admin.TabularInline):
    """Show credit ledger entries inline"""
    model = None  # Will be set dynamically
    extra = 0
    can_delete = False
    fields = ['ledger_id', 'transaction_date', 'total_amount', 'amount_paid', 'balance_outstanding', 'status',
              'due_date']
    readonly_fields = ['ledger_id', 'transaction_date', 'total_amount', 'amount_paid', 'balance_outstanding', 'status',
                       'due_date']

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = [
        'customer_number',
        'full_name',
        'phone',
        'email',
        'customer_type',
        'total_orders',
        'total_spent_display',
        'credit_limit_display',  # ✅ Show credit limit
        'credit_outstanding_display',  # ✅ Show outstanding balance
        'credit_status_badge',  # ✅ Show credit status
        'is_active',
    ]

    list_filter = [
        'customer_type',
        'is_active',
        'credit_status',  # ✅ Filter by credit status
        'created_at',
    ]

    search_fields = [
        'customer_number',
        'full_name',
        'phone',
        'email',
    ]

    readonly_fields = [
        'customer_number',
        'total_orders',
        'total_spent',
        'last_purchase_date',
        'created_at',
        'updated_at',
        'credit_outstanding_display',
        'credit_available_display',
    ]

    # ✅ IMPORTANT: Include credit fields in fieldsets
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'customer_number',
                'full_name',
                'customer_type',
                'phone',
                'email',
                'is_active',
            )
        }),
        ('Address', {
            'fields': (
                'address_line',
                'city',
                'state',
                'postal_code',
                'country',
            ),
            'classes': ('collapse',),
        }),
        ('Credit Settings', {  # ✅ NEW: Credit section
            'fields': (
                'credit_limit',
                'credit_terms_days',
                'credit_status',
                'credit_outstanding_display',
                'credit_available_display',
            ),
            'classes': ('wide',),
        }),
        ('Statistics', {
            'fields': (
                'total_orders',
                'total_spent',
                'last_purchase_date',
            ),
            'classes': ('collapse',),
        }),
        ('System', {
            'fields': (
                'created_by',
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',),
        }),
    )

    # inlines = [CustomerNoteInline]

    def total_spent_display(self, obj):
        total = obj.total_spent or 0
        return f"₦{total:,.2f}"

    total_spent_display.short_description = 'Total Spent'
    total_spent_display.admin_order_field = 'total_spent'

    def money(value):
        return f"₦{value:,.2f}"

    def credit_limit_display(self, obj):
        """Display credit limit with formatting"""
        from decimal import Decimal, InvalidOperation

        try:
            limit = Decimal(obj.credit_limit or 0)
        except (InvalidOperation, TypeError):
            limit = Decimal("0.00")

        formatted = f"₦{limit:,.2f}"

        if limit > 0:
            return format_html(
                '<span style="color:#0033A0;font-weight:bold;">{}</span>',
                formatted
            )

        return format_html('<span style="color:#999;">{}</span>', formatted)

    credit_limit_display.short_description = 'Credit Limit'
    credit_limit_display.admin_order_field = 'credit_limit'

    def credit_outstanding_display(self, obj):
        """Display outstanding credit balance"""
        from decimal import Decimal
        outstanding = obj.total_credit_outstanding
        outstanding = outstanding if isinstance(outstanding, Decimal) else Decimal(str(outstanding))

        if outstanding > 0:
            limit = obj.credit_limit if isinstance(obj.credit_limit, Decimal) else Decimal(str(obj.credit_limit))
            color = '#dc3545' if outstanding > limit * Decimal('0.8') else '#ffc107'
            formatted = f"₦{outstanding:,.2f}"

            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                color,
                formatted
            )
        return format_html('<span style="color: #28a745;">₦{}</span>', '0.00')

    credit_outstanding_display.short_description = 'Outstanding Balance'

    def credit_available_display(self, obj):
        """Display available credit"""
        from decimal import Decimal, InvalidOperation

        try:
            available = Decimal(obj.available_credit or 0)
        except (InvalidOperation, TypeError):
            available = Decimal("0.00")

        formatted = f"₦{available:,.2f}"

        if available > 0:
            return format_html("{}", formatted)

        return format_html('<span style="color:#dc3545;">{}</span>', formatted)

    credit_available_display.short_description = 'Available Credit'

    def credit_status_badge(self, obj):
        """Display credit status as colored badge"""
        status_colors = {
            'APPROVED': '#28a745',
            'SUSPENDED': '#ffc107',
            'BLOCKED': '#dc3545',
        }
        color = status_colors.get(obj.credit_status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            obj.get_credit_status_display()
        )

    credit_status_badge.short_description = 'Credit Status'
    credit_status_badge.admin_order_field = 'credit_status'

    def get_queryset(self, request):
        """Optimize queryset"""
        qs = super().get_queryset(request)
        # Add annotations if needed
        return qs

    actions = ['approve_credit', 'suspend_credit', 'block_credit', 'reset_credit_limit']

    def approve_credit(self, request, queryset):
        """Approve credit for selected customers"""
        count = queryset.update(credit_status='APPROVED')
        self.message_user(request, f'{count} customer(s) credit approved.')

    approve_credit.short_description = 'Approve credit for selected customers'

    def suspend_credit(self, request, queryset):
        """Suspend credit for selected customers"""
        count = queryset.update(credit_status='SUSPENDED')
        self.message_user(request, f'{count} customer(s) credit suspended.')

    suspend_credit.short_description = 'Suspend credit for selected customers'

    def block_credit(self, request, queryset):
        """Block credit for selected customers"""
        count = queryset.update(credit_status='BLOCKED')
        self.message_user(request, f'{count} customer(s) credit blocked.')

    block_credit.short_description = 'Block credit for selected customers'

    def reset_credit_limit(self, request, queryset):
        """Reset credit limit to zero"""
        count = queryset.update(credit_limit=0)
        self.message_user(request, f'{count} customer(s) credit limit reset to ₦0.')

    reset_credit_limit.short_description = 'Reset credit limit to ₦0'


@admin.register(CustomerNote)
class CustomerNoteAdmin(admin.ModelAdmin):
    list_display = ['customer', 'note_type', 'note_preview', 'created_by', 'created_at']
    list_filter = ['note_type', 'created_at']
    search_fields = ['customer__full_name', 'note']
    readonly_fields = ['created_at']

    def note_preview(self, obj):
        """Show first 50 characters of note"""
        if len(obj.note) > 50:
            return obj.note[:50] + '...'
        return obj.note

    note_preview.short_description = 'Note'


# ═══════════════════════════════════════════════════════════════════
# QUICK GUIDE: How to Set Credit Limits
# ═══════════════════════════════════════════════════════════════════
"""
TO SET CREDIT LIMIT FOR A CUSTOMER:

1. Go to Django Admin → Customers → Select a customer
2. In the "Credit Settings" section:
   - Set "Credit limit": e.g., 100000.00 (for ₦100,000)
   - Set "Credit terms days": e.g., 30 (for Net 30)
   - Set "Credit status": APPROVED
3. Save

OR use bulk actions:
1. Select multiple customers in the list
2. Choose "Approve credit for selected customers" from actions
3. This will set their credit_status to APPROVED

IMPORTANT NOTES:
- credit_limit = Maximum amount customer can owe at once
- credit_outstanding = Current amount customer owes
- available_credit = credit_limit - credit_outstanding
- Customer can only make credit sales if:
  * credit_status = 'APPROVED'
  * available_credit >= sale amount
"""