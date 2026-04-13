# apps/reports/services_comprehensive.py
"""
Comprehensive Report Service
Pulls from orders, customers, inventory, credit, sales, cashier sessions.
Drop-in replacement / extension to the existing ReportService.
"""
from __future__ import annotations

import io
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Sum, Count, Avg, F, Q
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from apps.catalog.models import ProductVariant
from apps.inventory.models import StockMovement
from apps.orders.models import Order, OrderItem, OrderPayment
from apps.sales.models import CashierSession
from apps.customers.models import Customer


def _nd(value) -> date:
    """Normalize to date."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d").date()
    raise ValueError(f"Invalid date: {value}")


def _dec(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


class ComprehensiveReportService:
    """
    Build the full report data dict and generate the Excel workbook.
    """

    @staticmethod
    def build_report_data(date_from, date_to) -> dict:
        date_from = _nd(date_from)
        date_to   = _nd(date_to)
        period_label = f"{date_from:%Y-%m-%d} to {date_to:%Y-%m-%d}"

        return {
            "period_label":      period_label,
            "date_from":         date_from,
            "date_to":           date_to,
            "sales_summary":     ComprehensiveReportService._sales_summary(date_from, date_to),
            "sales_detail_rows": ComprehensiveReportService._sales_detail_rows(date_from, date_to),
            "daily_trend":       ComprehensiveReportService._daily_trend(date_from, date_to),
            "inventory":         ComprehensiveReportService._inventory_data(date_from, date_to),
            "cashier_data":      ComprehensiveReportService._cashier_data(date_from, date_to),
            "customer_data":     ComprehensiveReportService._customer_data(date_from, date_to),
            "credit_aging":      ComprehensiveReportService._credit_aging(),
            "overdue_credit":    ComprehensiveReportService._overdue_credit(),
        }

    # ── Sales Summary ────────────────────────────────────────────────────────
    @staticmethod
    def _sales_summary(date_from: date, date_to: date) -> dict:
        orders = Order.objects.filter(
            status="COMPLETED",
            completed_at__date__range=(date_from, date_to),
        )

        agg = orders.aggregate(
            total_sales=Coalesce(Sum("total"), Decimal("0.00")),
            gross_sales=Coalesce(Sum("subtotal"), Decimal("0.00")),
            total_discounts=Coalesce(Sum("discount_amount"), Decimal("0.00")),
            total_orders=Count("id"),
            avg_order=Coalesce(Avg("total"), Decimal("0.00")),
        )

        items_agg = OrderItem.objects.filter(
            order__status="COMPLETED",
            order__completed_at__date__range=(date_from, date_to),
        ).aggregate(
            qty=Coalesce(Sum("quantity"), 0),
        )

        # Payment breakdown from OrderPayment records (cash/card/transfer collected)
        payments = OrderPayment.objects.filter(
            order__status="COMPLETED",
            order__completed_at__date__range=(date_from, date_to),
        ).values("payment_method").annotate(total=Coalesce(Sum("amount"), Decimal("0.00")))

        pay_map = {p["payment_method"]: p["total"] for p in payments}

        # Credit sales: total value of orders marked as CREDIT sale type
        credit_total = orders.filter(sale_type="CREDIT").aggregate(
            t=Coalesce(Sum("total"), Decimal("0.00"))
        )["t"]

        # For card/transfer: also check orders whose *only* payment method is card/transfer
        # (in case OrderPayment records exist but weren't captured above)
        for method in ("CARD", "TRANSFER"):
            if pay_map.get(method, Decimal("0.00")) == Decimal("0.00"):
                # Fall back: sum totals of non-credit orders where all payments use this method
                method_total = (
                    Order.objects.filter(
                        status="COMPLETED",
                        completed_at__date__range=(date_from, date_to),
                        sale_type="CASH",
                        order_payments__payment_method=method,
                    )
                    .distinct()
                    .aggregate(t=Coalesce(Sum("total"), Decimal("0.00")))["t"]
                )
                if method_total > Decimal("0.00"):
                    pay_map[method] = method_total

        net_sales = agg["gross_sales"] - agg["total_discounts"]

        # Customer counts
        unique_customers = (
            orders.exclude(customer__isnull=True)
            .values("customer").distinct().count()
        )
        walkins = orders.filter(customer__isnull=True).count()
        new_custs = Customer.objects.filter(
            id__in=list(
                orders.exclude(customer__isnull=True)
                .values_list("customer_id", flat=True).distinct()
            ),
            created_at__date__range=(date_from, date_to),
        ).count()

        # Product breakdown
        products = list(
            OrderItem.objects.filter(
                order__status="COMPLETED",
                order__completed_at__date__range=(date_from, date_to),
            )
            .values("product_name", "variant_name", "sku")
            .annotate(
                quantity_sold=Coalesce(Sum("quantity"), 0),
                revenue=Coalesce(Sum("line_total"), Decimal("0.00")),
            )
            .order_by("-revenue")
        )

        return {
            "total_orders":        agg["total_orders"],
            "total_items_sold":    items_agg["qty"],
            "total_sales":         agg["total_sales"],
            "gross_sales":         agg["gross_sales"],
            "net_sales":           net_sales,
            "total_discounts":     agg["total_discounts"],
            "average_order_value": agg["avg_order"],
            "cash_sales":          pay_map.get("CASH", Decimal("0.00")),
            "card_sales":          pay_map.get("CARD", Decimal("0.00")),
            "transfer_sales":      pay_map.get("TRANSFER", Decimal("0.00")),
            "credit_sales":        credit_total,
            "total_customers":     unique_customers,
            "new_customers":       new_custs,
            "returning_customers": max(unique_customers - new_custs, 0),
            "walk_in_sales":       walkins,
            "products":            products,
        }

    # ── Sales Detail Rows (template format) ──────────────────────────────────
    @staticmethod
    def _sales_detail_rows(date_from: date, date_to: date) -> list:
        """
        One row per order-line-item with:
        Order Number, Date, Cashier, Customer, Customer Type,
        Sales Person, Product, Variant, Unit Price, Quantity, Sub-Total, Payment Type
        """
        items = (
            OrderItem.objects
            .filter(
                order__status="COMPLETED",
                order__completed_at__date__range=(date_from, date_to),
            )
            .select_related(
                "order",
                "order__customer",
                "order__customer__sales_person",
                "order__created_by",
            )
            .order_by("order__completed_at", "order__order_number", "id")
        )

        rows = []
        for item in items:
            order = item.order
            customer = order.customer

            # Payment method(s) for this order
            pay_methods = list(
                order.order_payments.values_list("payment_method", flat=True).distinct()
            )
            if order.sale_type == "CREDIT":
                payment_type = "Credit"
            elif pay_methods:
                payment_type = "/".join(m.capitalize() for m in pay_methods)
            else:
                payment_type = "—"

            # Sales person
            sp = None
            if customer and hasattr(customer, "sales_person") and customer.sales_person:
                sp = customer.sales_person.full_name

            rows.append({
                "order_number":  order.order_number,
                "date":          order.completed_at.date() if order.completed_at else None,
                "cashier":       (order.created_by.get_full_name() or order.created_by.username
                                  if order.created_by else "—"),
                "customer":      customer.full_name if customer else "Walk-in",
                "customer_type": customer.get_customer_type_display() if customer else "Walk-in",
                "sales_person":  sp or "—",
                "product":       item.product_name,
                "variant":       item.variant_name,
                "unit_price":    item.unit_price,
                "quantity":      item.quantity,
                "line_total":    item.line_total,
                "payment_type":  payment_type,
            })

        return rows

    # ── Daily Trend ──────────────────────────────────────────────────────────
    @staticmethod
    def _daily_trend(date_from: date, date_to: date) -> list:
        rows = (
            Order.objects
            .filter(status="COMPLETED", completed_at__date__range=(date_from, date_to))
            .annotate(day=TruncDate("completed_at"))
            .values("day")
            .annotate(
                total_sales=Coalesce(Sum("total"), Decimal("0.00")),
                total_orders=Count("id"),
            )
            .order_by("day")
        )
        row_map = {r["day"]: r for r in rows}

        result = []
        current = date_from
        while current <= date_to:
            row = row_map.get(current)
            items_sold = (
                OrderItem.objects
                .filter(order__status="COMPLETED", order__completed_at__date=current)
                .aggregate(q=Coalesce(Sum("quantity"), 0))["q"]
            )
            result.append({
                "day":          current,
                "total_sales":  row["total_sales"]  if row else Decimal("0.00"),
                "total_orders": row["total_orders"] if row else 0,
                "total_items":  items_sold,
            })
            current += timedelta(days=1)
        return result

    # ── Inventory Data ────────────────────────────────────────────────────────
    @staticmethod
    def _inventory_data(date_from: date, date_to: date) -> dict:
        """
        Inventory reconciliation for the report period.

        Opening stock is derived from the stock_before of the earliest
        StockMovement in the period. If there are no movements at all,
        we reconstruct opening = actual_closing + sales_in_period
        (i.e. nothing was restocked or adjusted, only sold).

        Adj (+): non-sale increases in the period (restocks, positive corrections).
        Adj (-): non-sale decreases in the period (damages, negative corrections).
        Sales:   units sold via completed orders in the period.

        Expected closing = opening + adj_inc - adj_dec - sales
        Actual closing   = variant.stock_quantity  (live value from DB)
        Variance         = actual_closing - expected_closing
        """
        from django.db.models import F, Min

        variants = ProductVariant.objects.select_related(
            "product", "product__category"
        ).filter(product__is_active=True, is_active=True)

        products = []
        for variant in variants:

            # ── Units sold via completed orders in period ──────────────────
            sales = (
                OrderItem.objects.filter(
                    order__status="COMPLETED",
                    order__completed_at__date__range=(date_from, date_to),
                    variant=variant,
                ).aggregate(q=Coalesce(Sum("quantity"), 0))["q"] or 0
            )

            # ── Non-sale stock increases (restocks, positive adjustments) ──
            # quantity > 0 means stock went up (RESTOCK, CORRECTION up, etc.)
            adj_inc = (
                StockMovement.objects.filter(
                    variant=variant,
                    created_at__date__range=(date_from, date_to),
                    quantity__gt=0,
                ).aggregate(q=Coalesce(Sum("quantity"), 0))["q"] or 0
            )

            # ── Non-sale stock decreases (damage, negative adjustment) ────
            # quantity < 0 and NOT a SALE movement type
            adj_dec = abs(
                StockMovement.objects.filter(
                    variant=variant,
                    created_at__date__range=(date_from, date_to),
                    quantity__lt=0,
                ).exclude(
                    movement_type="SALE"
                ).aggregate(q=Coalesce(Sum("quantity"), 0))["q"] or 0
            )

            # ── Opening stock: stock_before of earliest movement in period ─
            # This is the most accurate source; avoids deriving from live stock.
            first_movement = (
                StockMovement.objects.filter(
                    variant=variant,
                    created_at__date__range=(date_from, date_to),
                ).order_by("created_at").values("stock_before").first()
            )

            actual_closing = variant.stock_quantity

            if first_movement is not None:
                # We have movement records — use stock_before of first event
                opening_stock = first_movement["stock_before"]
            else:
                # No movements at all in this period.
                # Opening = closing + sales (only thing that changed stock)
                opening_stock = actual_closing + sales

            expected_closing = opening_stock + adj_inc - adj_dec - sales
            variance         = actual_closing - expected_closing
            stock_value      = Decimal(str(actual_closing)) * variant.cost_price

            unit_price = (
                getattr(variant, "price", None)
                or getattr(variant, "selling_price", None)
                or getattr(variant, "unit_price", None)
                or Decimal("0.00")
            )

            products.append({
                "product_name":          variant.product.name,
                "variant_name":          variant.name or "Standard",
                "sku":                   variant.sku or "",
                "category":              variant.product.category.name if variant.product.category else "",
                "opening_stock":         opening_stock,
                "adjustments_increase":  adj_inc,
                "adjustments_decrease":  adj_dec,
                "sales":                 sales,
                "expected_closing":      expected_closing,
                "actual_closing":        actual_closing,
                "variance":              variance,
                "unit_price":            _dec(unit_price),
                "stock_value":           stock_value,
            })

        return {
            "total_products":              len(products),
            "total_opening_stock":         sum(p["opening_stock"] for p in products),
            "total_stock_added":           sum(p["adjustments_increase"] for p in products),
            "total_adjustments_increase":  sum(p["adjustments_increase"] for p in products),
            "total_adjustments_decrease":  sum(p["adjustments_decrease"] for p in products),
            "total_quantity_sold":         sum(p["sales"] for p in products),
            "total_expected_closing":      sum(p["expected_closing"] for p in products),
            "total_actual_closing":        sum(p["actual_closing"] for p in products),
            "total_variance":              sum(p["variance"] for p in products),
            "total_stock_value":           sum((p["stock_value"] for p in products), Decimal("0.00")),
            "products":                    products,
        }

    # ── Cashier Performance ───────────────────────────────────────────────────
    @staticmethod
    def _cashier_data(date_from: date, date_to: date) -> dict:
        orders = Order.objects.filter(
            status="COMPLETED",
            completed_at__date__range=(date_from, date_to),
        ).select_related("created_by")

        cashier_map: dict = {}
        for order in orders:
            user = order.created_by
            name = (user.get_full_name() or user.username) if user else "Unknown"
            if name not in cashier_map:
                cashier_map[name] = {
                    "cashier": name, "orders": 0, "items_sold": 0,
                    "revenue": Decimal("0.00"),
                    "first_sale": order.completed_at,
                    "last_sale":  order.completed_at,
                }
            s = cashier_map[name]
            s["orders"]    += 1
            s["revenue"]   += order.total
            s["items_sold"] += (
                order.items.aggregate(q=Coalesce(Sum("quantity"), 0))["q"]
            )
            if order.completed_at and order.completed_at < s["first_sale"]:
                s["first_sale"] = order.completed_at
            if order.completed_at and order.completed_at > s["last_sale"]:
                s["last_sale"] = order.completed_at

        cashiers = []
        for s in cashier_map.values():
            s["avg_order"] = s["revenue"] / s["orders"] if s["orders"] else Decimal("0.00")
            cashiers.append(s)
        cashiers.sort(key=lambda x: x["revenue"], reverse=True)

        sessions = CashierSession.objects.filter(
            opened_at__date__range=(date_from, date_to)
        ).select_related("cashier", "register", "store")

        session_data = []
        for sess in sessions:
            sess_orders = Order.objects.filter(cashier_session=sess, status="COMPLETED")
            session_data.append({
                "session":  sess.id,
                "store":    sess.store.name if sess.store else "",
                "register": sess.register.name if sess.register else "",
                "cashier":  (sess.cashier.get_full_name() or sess.cashier.username) if sess.cashier else "",
                "opened":   sess.opened_at,
                "closed":   sess.closed_at,
                "orders":   sess_orders.count(),
                "revenue":  sess_orders.aggregate(
                    t=Coalesce(Sum("total"), Decimal("0.00"))
                )["t"],
            })

        total_revenue = orders.aggregate(
            t=Coalesce(Sum("total"), Decimal("0.00"))
        )["t"]

        return {
            "summary": {
                "total_cashiers":  len(cashiers),
                "total_orders":    orders.count(),
                "total_revenue":   total_revenue,
                "total_sessions":  sessions.count(),
            },
            "cashiers":  cashiers,
            "sessions":  session_data,
        }

    # ── Customer Analysis ─────────────────────────────────────────────────────
    @staticmethod
    def _customer_data(date_from: date, date_to: date) -> dict:
        orders = Order.objects.filter(
            status="COMPLETED",
            completed_at__date__range=(date_from, date_to),
            customer__isnull=False,
        ).select_related("customer", "customer__sales_person")

        cmap: dict = {}
        for order in orders:
            cust = order.customer
            if cust.id not in cmap:
                sp = None
                if hasattr(cust, "sales_person") and cust.sales_person:
                    sp = cust.sales_person.full_name
                cmap[cust.id] = {
                    "customer":      cust.full_name,
                    "phone":         cust.phone or "",
                    "customer_type": cust.get_customer_type_display(),
                    "sales_person":  sp or "—",
                    "orders":        0,
                    "items":         0,
                    "revenue":       Decimal("0.00"),
                    "first_purchase": order.completed_at,
                    "last_purchase":  order.completed_at,
                }
            s = cmap[cust.id]
            s["orders"]  += 1
            s["revenue"] += order.total
            s["items"]   += (
                order.items.aggregate(q=Coalesce(Sum("quantity"), 0))["q"]
            )
            if order.completed_at and order.completed_at < s["first_purchase"]:
                s["first_purchase"] = order.completed_at
            if order.completed_at and order.completed_at > s["last_purchase"]:
                s["last_purchase"] = order.completed_at

        customers = []
        for s in cmap.values():
            s["avg_order"] = s["revenue"] / s["orders"] if s["orders"] else Decimal("0.00")
            customers.append(s)
        customers.sort(key=lambda x: x["revenue"], reverse=True)

        total_rev = sum((c["revenue"] for c in customers), Decimal("0.00"))
        return {
            "summary": {
                "total_customers":    len(customers),
                "total_revenue":      total_rev,
                "avg_customer_value": total_rev / len(customers) if customers else Decimal("0.00"),
            },
            "customers": customers,
        }

    # ── Credit Aging ──────────────────────────────────────────────────────────
    @staticmethod
    def _credit_aging() -> dict:
        try:
            from apps.credit.models import CreditLedger
        except ImportError:
            return {"date_range": "", "summary": {}, "customers": []}

        today = timezone.now().date()
        ledgers = CreditLedger.objects.filter(
            balance_outstanding__gt=0
        ).select_related("customer")

        cmap: dict = {}
        for entry in ledgers:
            cust = entry.customer
            if cust.id not in cmap:
                cmap[cust.id] = {
                    "customer": cust.full_name,
                    "phone":    cust.phone or "",
                    "current": Decimal("0.00"), "days_30": Decimal("0.00"),
                    "days_60": Decimal("0.00"), "days_90": Decimal("0.00"),
                    "days_120": Decimal("0.00"), "total": Decimal("0.00"),
                }
            s = cmap[cust.id]
            due = entry.due_date or today
            days = (today - due).days
            amt = entry.balance_outstanding
            if days <= 0:       s["current"]  += amt
            elif days <= 30:    s["days_30"]  += amt
            elif days <= 60:    s["days_60"]  += amt
            elif days <= 90:    s["days_90"]  += amt
            else:               s["days_120"] += amt
            s["total"] += amt

        customers = list(cmap.values())
        customers.sort(key=lambda x: x["total"], reverse=True)

        def tot(key):
            return sum((c[key] for c in customers), Decimal("0.00"))

        return {
            "date_range": f"As at {today:%Y-%m-%d}",
            "summary": {
                "total_outstanding": tot("total"),
                "current":  tot("current"),
                "days_30":  tot("days_30"),
                "days_60":  tot("days_60"),
                "days_90":  tot("days_90"),
                "days_120": tot("days_120"),
            },
            "customers": customers,
        }

    # ── Overdue Credit ────────────────────────────────────────────────────────
    @staticmethod
    def _overdue_credit() -> dict:
        try:
            from apps.credit.models import CreditLedger
        except ImportError:
            return {"date_range": "", "summary": {}, "rows": []}

        today = timezone.now().date()
        entries = CreditLedger.objects.filter(
            balance_outstanding__gt=0,
            due_date__lt=today,
        ).select_related("customer", "order")

        rows = []
        for e in entries:
            days = (today - e.due_date).days
            status = ("Reminder" if days <= 15 else
                      "Follow-up" if days <= 30 else
                      "Urgent"    if days <= 60 else "Critical")
            rows.append({
                "customer":    e.customer.full_name,
                "phone":       e.customer.phone or "",
                "invoice":     e.order.order_number if e.order else "",
                "due_date":    e.due_date,
                "days_overdue": days,
                "outstanding": e.balance_outstanding,
                "status":      status,
            })

        rows.sort(key=lambda x: x["days_overdue"], reverse=True)
        total = sum((r["outstanding"] for r in rows), Decimal("0.00"))
        return {
            "date_range": f"As at {today:%Y-%m-%d}",
            "summary": {
                "accounts":      len(rows),
                "total_overdue": total,
                "oldest_days":   max((r["days_overdue"] for r in rows), default=0),
            },
            "rows": rows,
        }

    # ── Excel generation ──────────────────────────────────────────────────────
    @staticmethod
    def generate_excel(date_from, date_to) -> bytes:
        """
        Build report data, export to Excel, return raw bytes.
        """
        from apps.reports.exporters.comprehensive_excel import ComprehensiveExcelExporter

        data = ComprehensiveReportService.build_report_data(date_from, date_to)
        exporter = ComprehensiveExcelExporter(data)
        wb = exporter.build()

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.read()