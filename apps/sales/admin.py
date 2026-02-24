# apps/sales/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import Store, Register, CashierSession


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ('Store Information', {
            'fields': ('name', 'address', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def total_registers(self, obj):
        count = obj.registers.filter(is_active=True).count()
        return format_html('<strong>{}</strong>', count)

    total_registers.short_description = 'Active Registers'

    actions = ['activate_stores', 'deactivate_stores']

    def activate_stores(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} store(s) activated.')

    activate_stores.short_description = 'Activate selected stores'

    def deactivate_stores(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} store(s) deactivated.')

    deactivate_stores.short_description = 'Deactivate selected stores'


@admin.register(Register)
class RegisterAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "store", "is_active")
    list_filter = ("store", "is_active")
    search_fields = ("name", "code")
    autocomplete_fields = ("store",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ('Register Information', {
            'fields': ('store', 'name', 'code', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def active_sessions(self, obj):
        count = obj.sessions.filter(closed_at__isnull=True).count()
        if count > 0:
            return format_html('<span style="color: green;">✓ {}</span>', count)
        return format_html('<span style="color: gray;">—</span>')

    active_sessions.short_description = 'Open Sessions'

    actions = ['activate_registers', 'deactivate_registers']

    def activate_registers(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} register(s) activated.')

    activate_registers.short_description = 'Activate selected registers'

    def deactivate_registers(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} register(s) deactivated.')

    deactivate_registers.short_description = 'Deactivate selected registers'


@admin.register(CashierSession)
class CashierSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "cashier", "register", "store", "opened_at", "closed_at")
    list_filter = ("register__store", "register", "closed_at")
    search_fields = ("cashier__username", "register__name", "register__code")
    autocomplete_fields = ("cashier", "register")

    # ✅ these belong here (CashierSession has opened_at/closed_at/store)
    readonly_fields = ("opened_at", "closed_at", "store", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        # ✅ ensure store always matches register.store
        obj.store = obj.register.store
        super().save_model(request, obj, form, change)

    fieldsets = (
        ('Session Information', {
            'fields': ('store', 'register', 'cashier')
        }),
        ('Cash Management', {
            'fields': ('opening_cash', 'closing_cash')
        }),
        ('Session Timeline', {
            'fields': ('opened_at', 'closed_at', 'session_duration')
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def cashier_name(self, obj):
        if obj.cashier.get_full_name():
            return obj.cashier.get_full_name()
        return obj.cashier.username

    cashier_name.short_description = 'Cashier'
    cashier_name.admin_order_field = 'cashier__username'

    def status_badge(self, obj):
        if obj.closed_at:
            return format_html(
                '<span style="background: #dc3545; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px;">CLOSED</span>'
            )
        return format_html(
            '<span style="background: #28a745; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px;">OPEN</span>'
        )

    status_badge.short_description = 'Status'

    def duration(self, obj):
        if obj.closed_at:
            delta = obj.closed_at - obj.opened_at
            hours = delta.total_seconds() / 3600
            return f'{hours:.1f} hrs'
        else:
            delta = timezone.now() - obj.opened_at
            hours = delta.total_seconds() / 3600
            return format_html('<span style="color: green;">{:.1f} hrs (ongoing)</span>', hours)

    duration.short_description = 'Duration'

    def session_duration(self, obj):
        if obj.closed_at:
            delta = obj.closed_at - obj.opened_at
            hours = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            return f'{hours} hours, {minutes} minutes'
        else:
            delta = timezone.now() - obj.opened_at
            hours = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            return f'{hours} hours, {minutes} minutes (ongoing)'

    session_duration.short_description = 'Session Duration'

    actions = ['close_sessions']

    def close_sessions(self, request, queryset):
        open_sessions = queryset.filter(closed_at__isnull=True)
        count = open_sessions.count()
        for session in open_sessions:
            session.closed_at = timezone.now()
            session.save()
        self.message_user(request, f'{count} session(s) closed.')

    close_sessions.short_description = 'Close selected open sessions'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('store', 'register', 'cashier')