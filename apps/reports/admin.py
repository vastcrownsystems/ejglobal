from django.contrib import admin
from apps.reports.models import (
    ReportTemplate,
    GeneratedReport,
    ReportSchedule,
    DailySalesReport,
    WeeklySalesReport,
    MonthlySalesReport,
    YearlySalesReport,
    ProductPerformanceReport,
    DailyInventoryReport,
)


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "report_type", "default_format", "frequency", "is_active")
    list_filter = ("default_format", "frequency", "is_active")
    search_fields = ("name", "report_type")


@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    list_display = (
        "report_number",
        "title",
        "report_template",
        "file_format",
        "status",
        "generated_by",
        "generated_at",
    )
    list_filter = ("status", "file_format", "report_template")
    search_fields = ("report_number", "title")
    readonly_fields = ("report_number", "generated_at", "completed_at", "processing_time", "file_size")


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ("report_template", "is_active", "last_run", "next_run", "created_by")


@admin.register(DailySalesReport)
class DailySalesReportAdmin(admin.ModelAdmin):
    list_display = ("report_date", "total_sales", "total_orders", "total_items_sold", "generated_at")
    date_hierarchy = "report_date"


@admin.register(WeeklySalesReport)
class WeeklySalesReportAdmin(admin.ModelAdmin):
    list_display = ("year", "week_number", "total_sales", "total_orders", "generated_at")


@admin.register(MonthlySalesReport)
class MonthlySalesReportAdmin(admin.ModelAdmin):
    list_display = ("year", "month_name", "total_sales", "total_orders", "generated_at")


@admin.register(YearlySalesReport)
class YearlySalesReportAdmin(admin.ModelAdmin):
    list_display = ("year", "total_sales", "total_orders", "generated_at")


@admin.register(ProductPerformanceReport)
class ProductPerformanceReportAdmin(admin.ModelAdmin):
    list_display = ("product_name", "variant_name", "report_type", "units_sold", "total_revenue", "period_end")


@admin.register(DailyInventoryReport)
class DailyInventoryReportAdmin(admin.ModelAdmin):
    list_display = ("report_date", "product", "variant", "opening_stock", "actual_closing", "variance", "revenue")
    list_filter = ("report_date",)