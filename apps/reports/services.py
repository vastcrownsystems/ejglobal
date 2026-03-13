from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.files import File
from django.db import transaction
from django.db.models import Sum, Count, Avg, F, Q, Value, DecimalField
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from apps.catalog.models import ProductVariant
from apps.credit.models import CreditLedger
from apps.inventory.models import StockMovement
from apps.orders.models import Order, OrderItem, OrderPayment
from apps.reports.models import (
    ReportTemplate,
    GeneratedReport,
    ReportSchedule,
    DailyInventoryReport,
)
from apps.sales.models import CashierSession
from apps.customers.models import Customer

from apps.reports.exporters.low_stock_excel import LowStockExcelExporter
from apps.reports.exporters.low_stock_pdf import LowStockPDFExporter
from apps.reports.exporters.daily_inventory_excel import DailyInventoryExcelExporter
from apps.reports.exporters.daily_inventory_pdf import DailyInventoryPDFExporter
from apps.reports.exporters.inventory_movement_excel import InventoryMovementExcelExporter
from apps.reports.exporters.inventory_movement_pdf import InventoryMovementPDFExporter
from apps.reports.exporters.sales_summary_excel import SalesSummaryExcelExporter
from apps.reports.exporters.sales_summary_pdf import SalesSummaryPDFExporter
from apps.reports.exporters.cashier_performance_excel import CashierPerformanceExcelExporter
from apps.reports.exporters.cashier_performance_pdf import CashierPerformancePDFExporter
from apps.reports.exporters.customer_analysis_excel import CustomerAnalysisExcelExporter
from apps.reports.exporters.customer_analysis_pdf import CustomerAnalysisPDFExporter
from apps.reports.exporters.credit_aging_excel import CreditAgingExcelExporter
from apps.reports.exporters.credit_aging_pdf import CreditAgingPDFExporter
from apps.reports.exporters.overdue_credit_excel import OverdueCreditExcelExporter
from apps.reports.exporters.overdue_credit_pdf import OverdueCreditPDFExporter


class ReportService:
    """
    Main reporting service.

    Responsibilities:
    - dashboard analytics
    - report dataset generation
    - exporter dispatch
    - generated report logging
    """

    EXPORTER_MAP = {
        "DAILY_INVENTORY": {
            "EXCEL": DailyInventoryExcelExporter,
            "PDF": DailyInventoryPDFExporter
        },
        "SALES_SUMMARY": {
            "EXCEL": SalesSummaryExcelExporter,
            "PDF": SalesSummaryPDFExporter,
        },
        "LOW_STOCK_ALERT": {
            "EXCEL": LowStockExcelExporter,
            "PDF": LowStockPDFExporter
        },
        "INVENTORY_MOVEMENT": {
            "EXCEL": InventoryMovementExcelExporter,
            "PDF": InventoryMovementPDFExporter,
        },
        "CASHIER_PERFORMANCE": {
            "EXCEL": CashierPerformanceExcelExporter,
            "PDF": CashierPerformancePDFExporter,
        },
        "CUSTOMER_ANALYSIS": {
            "EXCEL": CustomerAnalysisExcelExporter,
            "PDF": CustomerAnalysisPDFExporter,
        },
        "CREDIT_AGING": {
            "EXCEL": CreditAgingExcelExporter,
            "PDF": CreditAgingPDFExporter,
        },
        "OVERDUE_CREDIT": {
            "EXCEL": OverdueCreditExcelExporter,
            "PDF": OverdueCreditPDFExporter,
        }
    }

    @staticmethod
    def _normalize_date(value) -> date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            return datetime.strptime(value, "%Y-%m-%d").date()
        raise ValueError("Invalid date value")

    @staticmethod
    def _currency(value) -> Decimal:
        return value or Decimal("0.00")

    @staticmethod
    def _period_label(date_from: date, date_to: date) -> str:
        return f"{date_from:%Y-%m-%d} to {date_to:%Y-%m-%d}"

    @staticmethod
    def _completed_orders(date_from: date, date_to: date):
        return Order.objects.filter(
            status="COMPLETED",
            created_at__date__range=(date_from, date_to),
        )

    @staticmethod
    def _payment_breakdown(orders_qs):

        rows = (
            OrderPayment.objects.filter(order__in=orders_qs)
            .values("payment_method")
            .annotate(
                total=Coalesce(Sum("amount"), Decimal("0.00")),
                count=Count("id"),
            )
        )

        breakdown = {row["payment_method"]: row["total"] for row in rows}

        # credit orders (orders not fully paid)
        credit_sales = (
            orders_qs.filter(sale_type="CREDIT")
            .aggregate(total=Coalesce(Sum("total"), Decimal("0.00")))["total"]
        )

        return {
            "cash_sales": breakdown.get("CASH", Decimal("0.00")),
            "card_sales": breakdown.get("CARD", Decimal("0.00")),
            "transfer_sales": breakdown.get("TRANSFER", Decimal("0.00")),
            "credit_sales": credit_sales or Decimal("0.00"),
            "payment_breakdown": list(rows),
        }

    @staticmethod
    def get_sales_analytics(date_from, date_to):
        date_from = ReportService._normalize_date(date_from)
        date_to = ReportService._normalize_date(date_to)

        orders = ReportService._completed_orders(date_from, date_to)
        order_items = OrderItem.objects.filter(order__in=orders)

        sales_data = orders.aggregate(
            total_sales=Coalesce(Sum("total"), Decimal("0.00")),
            gross_sales=Coalesce(Sum("subtotal"), Decimal("0.00")),
            total_tax=Coalesce(Sum("tax_amount"), Decimal("0.00")),
            total_discounts=Coalesce(Sum("discount_amount"), Decimal("0.00")),
            average_order_value=Coalesce(
                Avg("total"),
                Value(Decimal("0.00"), output_field=DecimalField(max_digits=12, decimal_places=2)),
            ),
            total_orders=Count("id"),
        )

        total_items_sold = order_items.aggregate(
            total=Coalesce(Sum("quantity"), 0)
        )["total"] or 0

        distinct_customers = (
            orders.exclude(customer__isnull=True)
            .values("customer")
            .distinct()
            .count()
        )

        walk_in_sales = orders.filter(customer__isnull=True).count()

        customer_ids = list(
            orders.exclude(customer__isnull=True)
            .values_list("customer_id", flat=True)
            .distinct()
        )

        new_customers = Customer.objects.filter(
            id__in=customer_ids,
            created_at__date__range=(date_from, date_to),
        ).count()

        returning_customers = max(distinct_customers - new_customers, 0)

        payment = ReportService._payment_breakdown(orders)

        top_product = (
            order_items.values("product_name", "variant_name", "sku", "variant_id")
            .annotate(
                total_quantity=Coalesce(Sum("quantity"), 0),
                total_revenue=Coalesce(Sum("line_total"), Decimal("0.00")),
            )
            .order_by("-total_quantity", "-total_revenue")
            .first()
        )

        net_sales = sales_data["gross_sales"] - sales_data["total_discounts"]

        return {
            "period_start": date_from,
            "period_end": date_to,
            "period_days": (date_to - date_from).days + 1,
            "total_sales": sales_data["total_sales"],
            "gross_sales": sales_data["gross_sales"],
            "net_sales": net_sales,
            "total_tax": sales_data["total_tax"],
            "total_discounts": sales_data["total_discounts"],
            "average_order_value": sales_data["average_order_value"],
            "total_orders": sales_data["total_orders"],
            "total_items_sold": total_items_sold,
            "total_customers": distinct_customers,
            "new_customers": new_customers,
            "returning_customers": returning_customers,
            "walk_in_sales": walk_in_sales,
            "completed_orders": sales_data["total_orders"],
            "cancelled_orders": Order.objects.filter(
                status="CANCELLED",
                created_at__date__range=(date_from, date_to),
            ).count(),
            "refunded_orders": Order.objects.filter(
                payment_status="REFUNDED",
                created_at__date__range=(date_from, date_to),
            ).count(),
            "top_product": top_product,
            **payment,
        }

    @staticmethod
    def get_daily_breakdown(date_from, date_to):
        date_from = ReportService._normalize_date(date_from)
        date_to = ReportService._normalize_date(date_to)

        rows = (
            ReportService._completed_orders(date_from, date_to)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(
                total_sales=Coalesce(Sum("total"), Decimal("0.00")),
                total_orders=Count("id"),
                average_order=Coalesce(
                    Avg("total"),
                    Value(Decimal("0.00"), output_field=DecimalField(max_digits=12, decimal_places=2)),
                ),
            )
            .order_by("day")
        )

        row_map = {row["day"]: row for row in rows}

        output = []
        current = date_from
        while current <= date_to:
            row = row_map.get(current)
            output.append({
                "day": current,
                "total_sales": row["total_sales"] if row else Decimal("0.00"),
                "total_orders": row["total_orders"] if row else 0,
                "average_order": row["average_order"] if row else Decimal("0.00"),
                "total_items": (
                    OrderItem.objects.filter(
                        order__status="COMPLETED",
                        order__created_at__date=current,
                    ).aggregate(total=Coalesce(Sum("quantity"), 0))["total"] or 0
                ),
            })
            current += timedelta(days=1)

        return output

    @staticmethod
    def get_best_sellers(date_for=None, limit=5):
        report_date = date_for or timezone.now().date()
        return list(
            OrderItem.objects.filter(
                order__status="COMPLETED",
                order__created_at__date=report_date,
            )
            .values("product_name", "variant_name", "sku")
            .annotate(
                quantity_sold=Coalesce(Sum("quantity"), 0),
                revenue=Coalesce(Sum("line_total"), Decimal("0.00")),
            )
            .order_by("-quantity_sold", "-revenue")[:limit]
        )

    @staticmethod
    def get_inventory_summary(report_date=None):
        report_date = report_date or timezone.now().date()

        variants = ProductVariant.objects.filter(
            is_active=True,
            product__is_active=True,
            product__track_inventory=True,
        )

        items_out_of_stock = variants.filter(stock_quantity__lte=0).count()
        items_low_stock = variants.filter(
            stock_quantity__gt=0,
            stock_quantity__lte=F("low_stock_threshold"),
        ).count()

        items_with_variance = DailyInventoryReport.objects.filter(
            report_date=report_date
        ).exclude(variance=0).count()

        total_actual_closing = (
            DailyInventoryReport.objects.filter(report_date=report_date)
            .aggregate(total=Coalesce(Sum("actual_closing"), 0))["total"] or 0
        )

        return {
            "items_out_of_stock": items_out_of_stock,
            "items_low_stock": items_low_stock,
            "items_with_variance": items_with_variance,
            "total_actual_closing": total_actual_closing,
        }

    @staticmethod
    def build_dashboard_context(user):
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        recent_reports = GeneratedReport.objects.select_related("report_template").order_by("-generated_at")[:10]
        report_templates = ReportTemplate.objects.filter(is_active=True).order_by("name")
        scheduled_reports = ReportSchedule.objects.filter(is_active=True) if user.is_superuser else ReportSchedule.objects.none()

        return {
            "report_templates": report_templates,
            "recent_reports": recent_reports,
            "scheduled_reports": scheduled_reports,
            "is_admin": user.is_superuser,
            "today_sales": ReportService.get_sales_analytics(today, today),
            "week_sales": ReportService.get_sales_analytics(week_start, today),
            "month_sales": ReportService.get_sales_analytics(month_start, today),
            "inventory_summary": ReportService.get_inventory_summary(today),
            "best_sellers": ReportService.get_best_sellers(today, 5),
        }

    @staticmethod
    def generate_daily_inventory_data(date_from, date_to):
        date_from = ReportService._normalize_date(date_from)
        date_to = ReportService._normalize_date(date_to)

        report_date = date_to

        variants = ProductVariant.objects.select_related("product", "product__category").filter(
            product__is_active=True,
            is_active=True,
            product__track_inventory=True,
        )

        products = []
        for variant in variants:
            sales = (
                OrderItem.objects.filter(
                    order__status="COMPLETED",
                    order__created_at__date__range=(date_from, date_to),
                    variant=variant,
                ).aggregate(total=Coalesce(Sum("quantity"), 0))["total"] or 0
            )

            revenue = (
                OrderItem.objects.filter(
                    order__status="COMPLETED",
                    order__created_at__date__range=(date_from, date_to),
                    variant=variant,
                ).aggregate(total=Coalesce(Sum("line_total"), Decimal("0.00")))["total"]
                or Decimal("0.00")
            )

            added = (
                StockMovement.objects.filter(
                    variant=variant,
                    created_at__date__range=(date_from, date_to),
                    movement_type__in=["RESTOCK", "CORRECTION"],
                ).aggregate(total=Coalesce(Sum("quantity"), 0))["total"] or 0
            )

            adjustments_increase = (
                StockMovement.objects.filter(
                    variant=variant,
                    created_at__date__range=(date_from, date_to),
                    movement_type="ADJ",
                    stock_after__gt=F("stock_before"),
                ).aggregate(total=Coalesce(Sum("quantity"), 0))["total"] or 0
            )

            adjustments_decrease = (
                StockMovement.objects.filter(
                    variant=variant,
                    created_at__date__range=(date_from, date_to),
                    movement_type__in=["ADJ", "DAMAGE"],
                    stock_after__lt=F("stock_before"),
                ).aggregate(total=Coalesce(Sum("quantity"), 0))["total"] or 0
            )

            actual_closing = variant.stock_quantity
            opening_stock = actual_closing - added - adjustments_increase + adjustments_decrease + sales
            expected_closing = opening_stock + added + adjustments_increase - adjustments_decrease - sales
            variance = actual_closing - expected_closing
            stock_value = Decimal(actual_closing) * variant.cost_price

            products.append({
                "product_name": variant.product.name,
                "variant_name": variant.name or "Standard",
                "sku": variant.sku,
                "category": variant.product.category.name if variant.product.category else "",
                "opening_stock": opening_stock,
                "additions": added,
                "adjustments_increase": adjustments_increase,
                "adjustments_decrease": adjustments_decrease,
                "sales": sales,
                "expected_closing": expected_closing,
                "actual_closing": actual_closing,
                "variance": variance,
                "stock_value": stock_value,
                "revenue": revenue,
            })

            DailyInventoryReport.objects.update_or_create(
                report_date=report_date,
                product=variant.product,
                variant=variant,
                defaults={
                    "opening_stock": opening_stock,
                    "stock_added": added,
                    "stock_removed": adjustments_decrease,
                    "quantity_sold": sales,
                    "expected_closing": expected_closing,
                    "actual_closing": actual_closing,
                    "variance": variance,
                    "revenue": revenue,
                    "unit_price": variant.price,
                    "stock_value": stock_value,
                },
            )

        summary = {
            "total_products": len(products),
            "total_opening_stock": sum(p["opening_stock"] for p in products),
            "total_stock_added": sum(p["additions"] for p in products),
            "total_adjustments_increase": sum(p["adjustments_increase"] for p in products),
            "total_adjustments_decrease": sum(p["adjustments_decrease"] for p in products),
            "total_quantity_sold": sum(p["sales"] for p in products),
            "total_expected_closing": sum(p["expected_closing"] for p in products),
            "total_actual_closing": sum(p["actual_closing"] for p in products),
            "total_variance": sum(p["variance"] for p in products),
            "total_revenue": sum((p["stock_value"] for p in products), Decimal("0.00")),
        }

        return {
            "date_range": ReportService._period_label(date_from, date_to),
            "summary": summary,
            "products": products,
        }


    @staticmethod
    def build_report_data(report_type, date_from, date_to):
        if report_type == "DAILY_INVENTORY":
            return ReportService.generate_daily_inventory_data(date_from, date_to)
        if report_type == "SALES_SUMMARY":
            return ReportService.generate_sales_summary_data(date_from, date_to)
        if report_type == "CREDIT_AGING":
            return ReportService.generate_credit_aging_data(date_from, date_to)
        if report_type == "LOW_STOCK_ALERT":
            return ReportService.generate_low_stock_alert_data(date_from, date_to)
        if report_type == "INVENTORY_MOVEMENT":
            return ReportService.generate_inventory_movement_data(date_from, date_to)
        if report_type == "CASHIER_PERFORMANCE":
            return ReportService.generate_cashier_performance_data(date_from, date_to)
        if report_type == "CUSTOMER_ANALYSIS":
            return ReportService.generate_customer_analysis_data(date_from, date_to)
        if report_type == "CUSTOMER_ANALYSIS":
            return ReportService.generate_credit_aging_data(date_from, date_to)
        if report_type == "OVERDUE_CREDIT":
            return ReportService.generate_overdue_credit_data(date_from, date_to)

        raise ValueError(f"Unsupported report type: {report_type}")

    @staticmethod
    def get_exporter(report_type, file_format):
        format_key = file_format.upper()
        try:
            return ReportService.EXPORTER_MAP[report_type][format_key]
        except KeyError as exc:
            raise ValueError(f"No exporter configured for {report_type} / {file_format}") from exc

    @staticmethod
    @transaction.atomic
    def generate_report(report_template, generated_by, date_from, date_to, file_format=None, filters=None):
        date_from = ReportService._normalize_date(date_from)
        date_to = ReportService._normalize_date(date_to)
        chosen_format = (file_format or report_template.default_format or "EXCEL").upper()

        generated_report = GeneratedReport.objects.create(
            report_template=report_template,
            title=report_template.name,
            date_from=date_from,
            date_to=date_to,
            file_format=chosen_format,
            status="PROCESSING",
            generated_by=generated_by,
            filters_applied=filters or {},
        )

        started = time.perf_counter()

        try:
            report_data = ReportService.build_report_data(
                report_template.report_type,
                date_from,
                date_to,
            )

            exporter_class = ReportService.get_exporter(report_template.report_type, chosen_format)
            exporter = exporter_class()

            ext = "xlsx" if chosen_format == "EXCEL" else "pdf"
            filename = f"{generated_report.report_number}.{ext}"
            directory = os.path.join(settings.MEDIA_ROOT, "reports", timezone.now().strftime("%Y/%m"))
            os.makedirs(directory, exist_ok=True)
            path = os.path.join(directory, filename)

            exporter.export(report_data, path)

            with open(path, "rb") as fh:
                generated_report.file_path.save(filename, File(fh), save=False)

            generated_report.file_size = os.path.getsize(path)
            generated_report.status = "COMPLETED"
            generated_report.completed_at = timezone.now()
            generated_report.processing_time = round(time.perf_counter() - started, 3)
            generated_report.row_count = len(
                report_data.get("products")
                or report_data.get("aging_data")
                or report_data.get("top_products")
                or []
            )
            generated_report.save()

        except Exception as exc:
            generated_report.status = "FAILED"
            generated_report.error_message = str(exc)
            generated_report.processing_time = round(time.perf_counter() - started, 3)
            generated_report.completed_at = timezone.now()
            generated_report.save()
            raise

        return generated_report

    @staticmethod
    def seed_default_templates():
        templates = [
            {
                "report_type": "DAILY_INVENTORY",
                "name": "Daily Inventory Report",
                "description": "Opening stock, movements, sales, expected closing, actual closing, and variance.",
                "default_format": "EXCEL",
            },
            {
                "report_type": "SALES_SUMMARY",
                "name": "Sales Summary Report",
                "description": "Revenue, orders, top products, and category sales.",
                "default_format": "PDF",
            },
            {
                "report_type": "CREDIT_AGING",
                "name": "Credit Aging Report",
                "description": "Outstanding balances by aging buckets.",
                "default_format": "PDF",
            },
            {
                "report_type": "LOW_STOCK_ALERT",
                "name": "Low Stock Alert",
                "description": "Inventory below reorder threshold.",
                "default_format": "EXCEL",
            },
            {
                "report_type": "PRODUCT_PERFORMANCE",
                "name": "Product Performance Report",
                "description": "Product sales and revenue performance.",
                "default_format": "EXCEL",
            },
            {
                "report_type": "CASHIER_PERFORMANCE",
                "name": "Cashier Performance Report",
                "description": "Cashier sales and operational performance.",
                "default_format": "EXCEL",
            },
            {
                "report_type": "CUSTOMER_ANALYSIS",
                "name": "Customer Analysis Report",
                "description": "Customer buying patterns and value.",
                "default_format": "EXCEL",
            },
            {
                "report_type": "PROFIT_LOSS",
                "name": "Profit & Loss Report",
                "description": "Financial profitability summary.",
                "default_format": "PDF",
            },
            {
                "report_type": "OVERDUE_CREDIT",
                "name": "Overdue Credit Report",
                "description": "Past-due credit accounts requiring follow-up.",
                "default_format": "PDF",
            },
            {
                "report_type": "INVENTORY_MOVEMENT",
                "name": "Inventory Movement Report",
                "description": "Stock movement details by period.",
                "default_format": "EXCEL",
            },
        ]

        for item in templates:
            ReportTemplate.objects.update_or_create(
                report_type=item["report_type"],
                defaults=item,
            )

    @staticmethod
    def generate_low_stock_alert_data(date_from, date_to):

        from apps.catalog.models import ProductVariant

        variants = ProductVariant.objects.select_related(
            "product",
            "product__category"
        )

        low_stock = variants.filter(
            stock_quantity__lte=F("low_stock_threshold")
        )

        products = []

        out_of_stock = 0
        critical = 0

        for v in low_stock:

            shortage = v.low_stock_threshold - v.stock_quantity

            status = "LOW"

            if v.stock_quantity == 0:
                status = "OUT OF STOCK"
                out_of_stock += 1
            elif shortage >= v.low_stock_threshold * 0.5:
                status = "CRITICAL"
                critical += 1

            products.append({
                "product_name": v.product.name,
                "variant_name": v.name,
                "sku": v.sku,
                "category": v.product.category.name if v.product.category else "",
                "stock_quantity": v.stock_quantity,
                "reorder_level": v.low_stock_threshold,
                "difference": shortage,
                "status": status,
            })

        return {
            "date_range": f"{date_from} to {date_to}",  # ⭐ REQUIRED
            "summary": {
                "total_products": variants.count(),
                "low_stock_items": len(products),
                "out_of_stock": out_of_stock,
                "critical": critical,
            },
            "products": products
        }

    @staticmethod
    def generate_inventory_movement_data(date_from, date_to):

        movements = (
            StockMovement.objects
            .select_related("variant", "variant__product")
            .filter(created_at__date__range=(date_from, date_to))
            .order_by("-created_at")
        )

        rows = []

        for m in movements:
            rows.append({
                "date": m.created_at,
                "product_name": m.variant.product.name,
                "variant_name": m.variant.name or "Standard",
                "sku": m.variant.sku,
                "movement_type": m.movement_type,
                "quantity": m.quantity,
                "stock_before": m.stock_before,
                "stock_after": m.stock_after,
            })

        return {
            "date_range": ReportService._period_label(date_from, date_to),
            "summary": {
                "total_movements": len(rows)
            },
            "movements": rows
        }

    from django.db.models import Sum, Count
    from django.db.models.functions import Coalesce, TruncDate
    from decimal import Decimal

    @staticmethod
    def generate_sales_summary_data(date_from, date_to):

        date_from = ReportService._normalize_date(date_from)
        date_to = ReportService._normalize_date(date_to)

        # -----------------------------
        # TOP PRODUCTS
        # -----------------------------

        product_sales = (
            OrderItem.objects
            .filter(
                order__status="COMPLETED",
                order__created_at__date__range=(date_from, date_to)
            )
            .values(
                "variant__product__name",
                "variant__name",
                "variant__sku",
                "variant__price"
            )
            .annotate(
                quantity_sold=Coalesce(Sum("quantity"), 0),
                revenue=Coalesce(Sum("line_total"), Decimal("0.00"))
            )
            .order_by("-revenue")
        )

        products = []

        for p in product_sales:
            products.append({
                "product_name": p["variant__product__name"],
                "variant_name": p["variant__name"] or "Standard",
                "sku": p["variant__sku"],
                "quantity_sold": p["quantity_sold"],
                "unit_price": p["variant__price"],
                "revenue": p["revenue"],
            })

        # -----------------------------
        # DAILY SALES TREND
        # -----------------------------

        trend_qs = (
            Order.objects
            .filter(
                status="COMPLETED",
                created_at__date__range=(date_from, date_to)
            )
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(
                orders=Count("id"),
                revenue=Coalesce(Sum("total"), Decimal("0.00"))
            )
            .order_by("day")
        )

        trend = []

        for t in trend_qs:
            trend.append({
                "date": t["day"],
                "orders": t["orders"],
                "revenue": t["revenue"],
            })

        # -----------------------------
        # SUMMARY
        # -----------------------------

        total_orders = Order.objects.filter(
            status="COMPLETED",
            created_at__date__range=(date_from, date_to)
        ).count()

        total_items = sum(p["quantity_sold"] for p in products)

        total_revenue = sum((p["revenue"] for p in products), Decimal("0.00"))

        # ----------------------------------
        # PAYMENT BREAKDOWN
        # ----------------------------------

        orders_qs = Order.objects.filter(
            status="COMPLETED",
            created_at__date__range=(date_from, date_to)
        )

        payments = ReportService._payment_breakdown(orders_qs)

        cash_sales = payments["cash_sales"]
        card_sales = payments["card_sales"]
        transfer_sales = payments["transfer_sales"]
        credit_sales = payments["credit_sales"]

        total_paid = cash_sales + card_sales + transfer_sales
        credit_sold = credit_sales

        # ----------------------------------
        # SUMMARY
        # ----------------------------------

        summary = {
            "total_orders": total_orders,
            "total_items": total_items,
            "total_revenue": total_revenue,

            # payment methods
            "cash_sales": cash_sales,
            "card_sales": card_sales,
            "transfer_sales": transfer_sales,
            "credit_sales": credit_sales,

            # totals
            "total_paid": total_paid,
            "credit_sold": credit_sold,
        }

        return {
            "date_range": ReportService._period_label(date_from, date_to),
            "summary": summary,
            "products": products,
            "trend": trend
        }

    @staticmethod
    def generate_cashier_performance_data(date_from, date_to):

        date_from = ReportService._normalize_date(date_from)
        date_to = ReportService._normalize_date(date_to)

        orders = Order.objects.filter(
            status="COMPLETED",
            created_at__date__range=(date_from, date_to)
        )

        cashier_stats = {}

        for order in orders.select_related("created_by"):

            cashier = order.created_by
            name = cashier.get_full_name() or cashier.username

            if name not in cashier_stats:
                cashier_stats[name] = {
                    "cashier": name,
                    "orders": 0,
                    "items_sold": 0,
                    "revenue": Decimal("0.00"),
                    "first_sale": order.created_at,
                    "last_sale": order.created_at
                }

            stat = cashier_stats[name]

            stat["orders"] += 1
            stat["revenue"] += order.total

            items = order.items.aggregate(q=Coalesce(Sum("quantity"), 0))["q"]
            stat["items_sold"] += items

            if order.created_at < stat["first_sale"]:
                stat["first_sale"] = order.created_at

            if order.created_at > stat["last_sale"]:
                stat["last_sale"] = order.created_at

        cashier_list = []

        for stat in cashier_stats.values():
            avg_order = stat["revenue"] / stat["orders"] if stat["orders"] else 0

            cashier_list.append({
                "cashier": stat["cashier"],
                "orders": stat["orders"],
                "items_sold": stat["items_sold"],
                "revenue": stat["revenue"],
                "avg_order": avg_order,
                "first_sale": stat["first_sale"],
                "last_sale": stat["last_sale"],
            })

        sessions = CashierSession.objects.filter(
            opened_at__date__range=(date_from, date_to)
        ).select_related("cashier", "register")

        session_data = []

        for s in sessions:
            orders_qs = Order.objects.filter(
                cashier_session=s,
                status="COMPLETED"
            )

            orders_count = orders_qs.count()

            revenue = orders_qs.aggregate(
                total=Coalesce(Sum("total"), Decimal("0.00"))
            )["total"]

            session_data.append({
                "session": s.id,
                "store": s.store.name,
                "register": s.register.name,
                "cashier": s.cashier.get_full_name() or s.cashier.username,
                "opened": s.opened_at,
                "closed": s.closed_at,
                "orders": orders_count,
                "revenue": revenue,
            })

        summary = {
            "total_cashiers": len(cashier_list),
            "total_orders": orders.count(),
            "total_revenue": orders.aggregate(
                total=Coalesce(Sum("total"), Decimal("0.00"))
            )["total"],
            "total_sessions": sessions.count()
        }

        return {
            "date_range": ReportService._period_label(date_from, date_to),
            "summary": summary,
            "cashiers": cashier_list,
            "sessions": session_data
        }

    @staticmethod
    def generate_customer_analysis_data(date_from, date_to):

        date_from = ReportService._normalize_date(date_from)
        date_to = ReportService._normalize_date(date_to)

        orders = (
            Order.objects
            .filter(
                status="COMPLETED",
                created_at__date__range=(date_from, date_to),
                customer__isnull=False
            )
            .select_related("customer")
        )

        customer_map = {}

        for order in orders:

            customer = order.customer

            if customer.id not in customer_map:
                customer_map[customer.id] = {
                    "customer": getattr(customer, "name", str(customer)),
                    "phone": getattr(customer, "phone", ""),
                    "orders": 0,
                    "items": 0,
                    "revenue": Decimal("0.00"),
                    "first_purchase": order.created_at,
                    "last_purchase": order.created_at,
                }

            stat = customer_map[customer.id]

            stat["orders"] += 1
            stat["revenue"] += order.total

            qty = order.items.aggregate(
                total=Coalesce(Sum("quantity"), 0)
            )["total"]

            stat["items"] += qty

            if order.created_at < stat["first_purchase"]:
                stat["first_purchase"] = order.created_at

            if order.created_at > stat["last_purchase"]:
                stat["last_purchase"] = order.created_at

        customers = list(customer_map.values())

        # calculate average order per customer
        for c in customers:
            c["avg_order"] = (
                c["revenue"] / c["orders"] if c["orders"] else Decimal("0.00")
            )

        customers.sort(key=lambda x: x["revenue"], reverse=True)

        total_revenue = sum((c["revenue"] for c in customers), Decimal("0.00"))

        summary = {
            "total_customers": len(customers),
            "total_revenue": total_revenue,
            "avg_customer_value": (
                total_revenue / len(customers)
                if customers else Decimal("0.00")
            )
        }

        return {
            "date_range": ReportService._period_label(date_from, date_to),
            "summary": summary,
            "customers": customers
        }

    @staticmethod
    def generate_credit_aging_data(date_from, date_to):

        today = timezone.now().date()

        ledgers = CreditLedger.objects.filter(
            balance_outstanding__gt=0
        ).select_related("customer")

        customer_map = {}

        for entry in ledgers:

            customer = entry.customer

            if customer.id not in customer_map:
                customer_map[customer.id] = {
                    "customer": getattr(customer, "name", str(customer)),
                    "phone": getattr(customer, "phone", ""),
                    "current": Decimal("0.00"),
                    "days_30": Decimal("0.00"),
                    "days_60": Decimal("0.00"),
                    "days_90": Decimal("0.00"),
                    "days_120": Decimal("0.00"),
                    "total": Decimal("0.00")
                }

            stat = customer_map[customer.id]

            due_date = entry.due_date or today
            days = (today - due_date).days

            amount = entry.balance_outstanding

            if days <= 0:
                stat["current"] += amount

            elif days <= 30:
                stat["days_30"] += amount

            elif days <= 60:
                stat["days_60"] += amount

            elif days <= 90:
                stat["days_90"] += amount

            else:
                stat["days_120"] += amount

            stat["total"] += amount

        customers = list(customer_map.values())

        summary = {
            "total_outstanding": sum((c["total"] for c in customers), Decimal("0.00")),
            "current": sum((c["current"] for c in customers), Decimal("0.00")),
            "days_30": sum((c["days_30"] for c in customers), Decimal("0.00")),
            "days_60": sum((c["days_60"] for c in customers), Decimal("0.00")),
            "days_90": sum((c["days_90"] for c in customers), Decimal("0.00")),
            "days_120": sum((c["days_120"] for c in customers), Decimal("0.00")),
        }

        return {
            "date_range": "As at " + today.strftime("%Y-%m-%d"),
            "summary": summary,
            "customers": customers
        }

    @staticmethod
    def generate_overdue_credit_data(date_from, date_to):

        today = timezone.now().date()

        entries = CreditLedger.objects.filter(
            balance_outstanding__gt=0,
            due_date__lt=today
        ).select_related("customer", "order")

        rows = []

        for e in entries:

            days_overdue = (today - e.due_date).days

            if days_overdue <= 15:
                status = "Reminder"
            elif days_overdue <= 30:
                status = "Follow-up"
            elif days_overdue <= 60:
                status = "Urgent"
            else:
                status = "Critical"

            rows.append({
                "customer": getattr(e.customer, "name", str(e.customer)),
                "phone": getattr(e.customer, "phone", ""),
                "invoice": getattr(e.order, "order_number", ""),
                "due_date": e.due_date,
                "days_overdue": days_overdue,
                "outstanding": e.balance_outstanding,
                "status": status
            })

        total_overdue = sum((r["outstanding"] for r in rows), Decimal("0.00"))

        summary = {
            "accounts": len(rows),
            "total_overdue": total_overdue,
            "oldest_days": max((r["days_overdue"] for r in rows), default=0)
        }

        return {
            "date_range": "As at " + today.strftime("%Y-%m-%d"),
            "summary": summary,
            "rows": rows
        }