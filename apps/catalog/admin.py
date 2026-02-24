from decimal import Decimal, InvalidOperation

from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import (
    Category,
    Product,
    VariantAttribute,
    VariantAttributeValue,
    ProductVariant,
)


# ----------------------------
# Helpers (safe Decimal)
# ----------------------------
def to_decimal(value, default="0.00") -> Decimal:
    try:
        if value is None:
            return Decimal(default)
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


# ----------------------------
# Category Admin
# ----------------------------
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "is_active", "display_order", "products_count")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_products_count=Count("products"))

    @admin.display(description="Products", ordering="_products_count")
    def products_count(self, obj):
        return obj._products_count


# ----------------------------
# Product Variant Inline
# ----------------------------
class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ("name", "price", "cost_price", "stock_quantity", "is_active", "is_default")
    readonly_fields = ()
    show_change_link = True


# ----------------------------
# Product Admin
# ----------------------------
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "sku", "base_price", "track_inventory", "is_active", "variants_count")
    list_filter = ("is_active", "track_inventory", "category")
    search_fields = ("name", "slug", "sku")
    autocomplete_fields = ("category",)
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    inlines = (ProductVariantInline,)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_variants_count=Count("variants"))

    @admin.display(description="Variants", ordering="_variants_count")
    def variants_count(self, obj):
        return obj._variants_count


# ----------------------------
# Variant Attribute Admin
# ----------------------------
@admin.register(VariantAttribute)
class VariantAttributeAdmin(admin.ModelAdmin):
    list_display = ("name", "display_name", "display_order", "created_at")
    search_fields = ("name", "display_name")
    ordering = ("display_order", "name")
    readonly_fields = ("created_at", "updated_at")


# ----------------------------
# Variant Attribute Value Admin
# ----------------------------
@admin.register(VariantAttributeValue)
class VariantAttributeValueAdmin(admin.ModelAdmin):
    list_display = ("attribute", "value", "display_order", "created_at")
    list_filter = ("attribute",)
    search_fields = ("attribute__name", "attribute__display_name", "value")
    autocomplete_fields = ("attribute",)
    ordering = ("attribute", "display_order", "value")
    readonly_fields = ("created_at", "updated_at")


# ----------------------------
# Product Variant Admin
# ----------------------------
@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "variant_name",
        "attributes_display",
        "price_display",
        "cost_display",
        "profit_display",
        "stock_display",
        "is_active",
        "is_default",
    )
    list_filter = ("is_active", "is_default", "product__category")
    search_fields = ("product__name", "sku", "barcode", "name", "attribute_values__value")
    autocomplete_fields = ("product",)  # ✅ only FK fields
    filter_horizontal = ("attribute_values",)  # ✅ best UX for ManyToMany
    readonly_fields = ("created_at", "updated_at")
    ordering = ("product", "name")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("product", "product__category").prefetch_related("attribute_values__attribute")

    @admin.display(description="Variant")
    def variant_name(self, obj):
        return obj.name or "Auto"

    @admin.display(description="Attributes")
    def attributes_display(self, obj):
        # Uses your model method (already correct)
        return obj.get_attribute_display()

    @admin.display(description="Price")
    def price_display(self, obj):
        price = to_decimal(obj.price)
        return format_html("₦{}", f"{price:,.2f}")

    @admin.display(description="Cost")
    def cost_display(self, obj):
        cost = to_decimal(obj.cost_price)
        return format_html("₦{}", f"{cost:,.2f}")

    @admin.display(description="Profit")
    def profit_display(self, obj):
        price = to_decimal(obj.price)
        cost = to_decimal(obj.cost_price)
        profit = price - cost

        margin = to_decimal(getattr(obj, "profit_margin", 0), default="0")

        if margin >= 50:
            color = "#198754"
        elif margin >= 20:
            color = "#fd7e14"
        else:
            color = "#dc3545"

        profit_str = f"{profit:,.2f}"
        margin_str = f"{float(margin):.1f}"

        # NOTE: no {:,.2f} or {:.1f} inside format_html anymore ✅
        return format_html(
            '<span style="color:{};">₦{} ({}%)</span>',
            color,
            profit_str,
            margin_str,
        )

    @admin.display(description="Stock")
    def stock_display(self, obj):
        if not obj.product.track_inventory:
            return format_html('<span style="color:#6c757d;">Not tracked</span>')

        qty = obj.stock_quantity
        if qty <= 0:
            return format_html('<span style="color:#dc3545;font-weight:700;">{} (Out)</span>', qty)

        if qty <= obj.low_stock_threshold:
            return format_html('<span style="color:#fd7e14;font-weight:700;">{} (Low)</span>', qty)

        return format_html('<span style="color:#198754;font-weight:700;">{}</span>', qty)
