# apps/reports/services.py - Reports Service

from django.db import transaction
from django.db.models import Sum, Count, Avg, Q, F, Max
from django.utils import timezone
from datetime import datetime, timedelta, date
from decimal import Decimal
import calendar
import logging

from .models import (
    DailySalesReport,
    WeeklySalesReport,
    MonthlySalesReport,
    YearlySalesReport,
    ProductPerformanceReport
)
from apps.orders.models import Order, OrderPayment
from apps.customers.models import Customer
from apps.catalog.models import Product, ProductVariant

logger = logging.getLogger(__name__)


class ReportService:
    """Service for generating sales reports"""

    @staticmethod
    @transaction.atomic
    def generate_daily_report(report_date=None, user=None):
        """
        Generate daily sales report

        Args:
            report_date: Date for report (default: yesterday)
            user: User generating report

        Returns:
            DailySalesReport instance
        """
        if report_date is None:
            report_date = (timezone.now() - timedelta(days=1)).date()

        logger.info(f"Generating daily report for {report_date}")

        # Get or create report
        report, created = DailySalesReport.objects.get_or_create(
            report_date=report_date,
            defaults={'generated_by': user}
        )

        # Get completed orders for the day
        orders = Order.objects.filter(
            status='COMPLETED',
            completed_at__date=report_date
        )

        # Calculate metrics
        aggregates = orders.aggregate(
            total_sales=Sum('total'),
            total_orders=Count('id'),
            avg_order_value=Avg('total'),
            gross_sales=Sum('subtotal'),
            total_discounts=Sum('discount_amount'),
            total_tax=Sum('tax_amount'),
        )


        # Calculate total items from OrderItem
        from apps.orders.models import OrderItem
        total_items = OrderItem.objects.filter(
            order__in=orders
        ).aggregate(total=Sum('quantity'))['total'] or 0

        # Update report
        report.total_sales = aggregates['total_sales'] or 0
        report.total_orders = aggregates['total_orders'] or 0
        report.total_items_sold = total_items
        report.average_order_value = aggregates['avg_order_value'] or 0
        report.gross_sales = aggregates['gross_sales'] or 0
        report.total_discounts = aggregates['total_discounts'] or 0
        report.total_tax = aggregates['total_tax'] or 0
        report.net_sales = report.gross_sales - report.total_discounts

        # Payment method breakdown
        payments = OrderPayment.objects.filter(
            order__in=orders
        ).values('payment_method').annotate(
            total=Sum('amount')
        )

        for payment in payments:
            method = payment['payment_method']
            amount = payment['total'] or 0

            if method == 'CASH':
                report.cash_sales = amount
            elif method == 'CARD':
                report.card_sales = amount
            elif method == 'TRANSFER':
                report.transfer_sales = amount
            elif method == 'MOBILE':
                report.mobile_sales = amount

        # Customer metrics
        customer_orders = orders.exclude(customer__isnull=True)
        report.total_customers = customer_orders.values('customer').distinct().count()
        report.walk_in_sales = orders.filter(customer__isnull=True).count()

        # New vs returning customers
        customer_ids = customer_orders.values_list('customer_id', flat=True)
        new_customers = Customer.objects.filter(
            id__in=customer_ids,
            created_at__date=report_date
        ).count()
        report.new_customers = new_customers
        report.returning_customers = report.total_customers - new_customers

        # Order status
        report.completed_orders = orders.count()
        report.cancelled_orders = Order.objects.filter(
            status='CANCELLED',
            updated_at__date=report_date
        ).count()

        # Sessions
        from apps.sales.models import CashierSession
        sessions = CashierSession.objects.filter(
            opened_at__date=report_date
        )
        report.sessions_count = sessions.count()
        report.unique_cashiers = sessions.values('cashier').distinct().count()

        # Top selling product
        top_product = ReportService._get_top_selling_product(
            report_date,
            report_date
        )

        if top_product:
            report.top_selling_product_id = top_product['variant__id']
            report.top_selling_product_name = top_product['variant__product__name']
            report.top_selling_product_quantity = top_product['total_quantity']

        # Detailed breakdown (JSON)
        report.report_data = {
            'hourly_sales': ReportService._get_hourly_breakdown(report_date),
            'payment_breakdown': {
                'cash': float(report.cash_sales),
                'card': float(report.card_sales),
                'transfer': float(report.transfer_sales),
                'mobile': float(report.mobile_sales),
            },
            'customer_type_breakdown': {
                'registered': report.total_customers,
                'walk_in': report.walk_in_sales,
            }
        }

        report.save()

        logger.info(f"Daily report generated: {report_date} - ₦{report.total_sales}")

        return report

    @staticmethod
    @transaction.atomic
    def generate_weekly_report(year, week_number, user=None):
        """
        Generate weekly sales report

        Args:
            year: Year
            week_number: Week number (1-52)
            user: User generating report

        Returns:
            WeeklySalesReport instance
        """
        # Calculate week start and end dates
        first_day = date(year, 1, 1)
        week_start = first_day + timedelta(weeks=week_number - 1)
        week_start = week_start - timedelta(days=week_start.weekday())
        week_end = week_start + timedelta(days=6)

        logger.info(f"Generating weekly report for Week {week_number}, {year}")

        # Get or create report
        report, created = WeeklySalesReport.objects.get_or_create(
            year=year,
            week_number=week_number,
            defaults={
                'week_start_date': week_start,
                'week_end_date': week_end,
                'generated_by': user
            }
        )

        # Get orders for the week
        orders = Order.objects.filter(
            status='COMPLETED',
            completed_at__date__gte=week_start,
            completed_at__date__lte=week_end
        )

        # Calculate metrics
        aggregates = orders.aggregate(
            total_sales=Sum('total'),
            total_orders=Count('id'),
            avg_order_value=Avg('total'),
            gross_sales=Sum('subtotal'),
            total_discounts=Sum('discount_amount'),
            total_tax=Sum('tax_amount'),
        )


        # Calculate total items from OrderItem
        from apps.orders.models import OrderItem
        total_items = OrderItem.objects.filter(
            order__in=orders
        ).aggregate(total=Sum('quantity'))['total'] or 0

        report.total_sales = aggregates['total_sales'] or 0
        report.total_orders = aggregates['total_orders'] or 0
        report.total_items_sold = total_items
        report.average_order_value = aggregates['avg_order_value'] or 0
        report.gross_sales = aggregates['gross_sales'] or 0
        report.total_discounts = aggregates['total_discounts'] or 0
        report.total_tax = aggregates['total_tax'] or 0
        report.net_sales = report.gross_sales - report.total_discounts
        report.daily_average_sales = report.total_sales / 7

        # Payment methods
        payments = OrderPayment.objects.filter(
            order__in=orders
        ).values('payment_method').annotate(total=Sum('amount'))

        for payment in payments:
            method = payment['payment_method']
            amount = payment['total'] or 0

            if method == 'CASH':
                report.cash_sales = amount
            elif method == 'CARD':
                report.card_sales = amount
            elif method == 'TRANSFER':
                report.transfer_sales = amount
            elif method == 'MOBILE':
                report.mobile_sales = amount

        # Customer metrics
        customer_orders = orders.exclude(customer__isnull=True)
        report.total_customers = customer_orders.values('customer').distinct().count()

        new_customers = Customer.objects.filter(
            created_at__date__gte=week_start,
            created_at__date__lte=week_end
        ).count()
        report.new_customers = new_customers

        # Growth calculation (vs previous week)
        prev_week_number = week_number - 1 if week_number > 1 else 52
        prev_year = year if week_number > 1 else year - 1

        try:
            prev_report = WeeklySalesReport.objects.get(
                year=prev_year,
                week_number=prev_week_number
            )

            if prev_report.total_sales > 0:
                report.sales_growth_percentage = (
                        ((report.total_sales - prev_report.total_sales) / prev_report.total_sales) * 100
                )

            if prev_report.total_orders > 0:
                report.order_growth_percentage = (
                        ((report.total_orders - prev_report.total_orders) / prev_report.total_orders) * 100
                )
        except WeeklySalesReport.DoesNotExist:
            pass

        # Daily breakdown
        daily_data = []
        current_date = week_start
        while current_date <= week_end:
            day_orders = orders.filter(completed_at__date=current_date)
            daily_data.append({
                'date': current_date.isoformat(),
                'day_name': current_date.strftime('%A'),
                'sales': float(day_orders.aggregate(total=Sum('total'))['total'] or 0),
                'orders': day_orders.count()
            })
            current_date += timedelta(days=1)

        report.report_data = {
            'daily_breakdown': daily_data,
        }

        report.save()

        logger.info(f"Weekly report generated: Week {week_number}, {year} - ₦{report.total_sales}")

        return report

    @staticmethod
    @transaction.atomic
    def generate_monthly_report(year, month, user=None):
        """
        Generate monthly sales report

        Args:
            year: Year
            month: Month (1-12)
            user: User generating report

        Returns:
            MonthlySalesReport instance
        """
        month_name = calendar.month_name[month]

        logger.info(f"Generating monthly report for {month_name} {year}")

        # Get or create report
        report, created = MonthlySalesReport.objects.get_or_create(
            year=year,
            month=month,
            defaults={
                'month_name': month_name,
                'generated_by': user
            }
        )

        # Date range
        month_start = date(year, month, 1)
        month_end = date(year, month, calendar.monthrange(year, month)[1])

        # Get orders for the month
        orders = Order.objects.filter(
            status='COMPLETED',
            completed_at__date__gte=month_start,
            completed_at__date__lte=month_end
        )

        # Calculate metrics
        aggregates = orders.aggregate(
            total_sales=Sum('total'),
            total_orders=Count('id'),
            avg_order_value=Avg('total'),
            gross_sales=Sum('subtotal'),
            total_discounts=Sum('discount_amount'),
            total_tax=Sum('tax_amount'),
        )


        # Calculate total items from OrderItem
        from apps.orders.models import OrderItem
        total_items = OrderItem.objects.filter(
            order__in=orders
        ).aggregate(total=Sum('quantity'))['total'] or 0

        report.total_sales = aggregates['total_sales'] or 0
        report.total_orders = aggregates['total_orders'] or 0
        report.total_items_sold = total_items
        report.average_order_value = aggregates['avg_order_value'] or 0
        report.gross_sales = aggregates['gross_sales'] or 0
        report.total_discounts = aggregates['total_discounts'] or 0
        report.total_tax = aggregates['total_tax'] or 0
        report.net_sales = report.gross_sales - report.total_discounts

        days_in_month = (month_end - month_start).days + 1
        report.daily_average_sales = report.total_sales / days_in_month if days_in_month > 0 else 0

        # Payment methods
        payments = OrderPayment.objects.filter(
            order__in=orders
        ).values('payment_method').annotate(total=Sum('amount'))

        for payment in payments:
            method = payment['payment_method']
            amount = payment['total'] or 0

            if method == 'CASH':
                report.cash_sales = amount
            elif method == 'CARD':
                report.card_sales = amount
            elif method == 'TRANSFER':
                report.transfer_sales = amount
            elif method == 'MOBILE':
                report.mobile_sales = amount

        # Customer metrics
        customer_orders = orders.exclude(customer__isnull=True)
        report.total_customers = customer_orders.values('customer').distinct().count()

        new_customers = Customer.objects.filter(
            created_at__date__gte=month_start,
            created_at__date__lte=month_end
        ).count()
        report.new_customers = new_customers

        # Growth (vs previous month)
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1

        try:
            prev_report = MonthlySalesReport.objects.get(
                year=prev_year,
                month=prev_month
            )

            if prev_report.total_sales > 0:
                report.sales_growth_percentage = (
                        ((report.total_sales - prev_report.total_sales) / prev_report.total_sales) * 100
                )

            if prev_report.total_orders > 0:
                report.order_growth_percentage = (
                        ((report.total_orders - prev_report.total_orders) / prev_report.total_orders) * 100
                )
        except MonthlySalesReport.DoesNotExist:
            pass

        # Best sales day
        best_day = orders.values('completed_at__date').annotate(
            total=Sum('total')
        ).order_by('-total').first()

        if best_day:
            report.best_sales_day = best_day['completed_at__date']
            report.best_sales_amount = best_day['total']

        # Daily breakdown
        daily_data = []
        current_date = month_start
        while current_date <= month_end:
            day_orders = orders.filter(completed_at__date=current_date)
            daily_data.append({
                'date': current_date.isoformat(),
                'day': current_date.day,
                'sales': float(day_orders.aggregate(total=Sum('total'))['total'] or 0),
                'orders': day_orders.count()
            })
            current_date += timedelta(days=1)

        report.report_data = {
            'daily_breakdown': daily_data,
        }

        report.save()

        logger.info(f"Monthly report generated: {month_name} {year} - ₦{report.total_sales}")

        return report

    @staticmethod
    @transaction.atomic
    def generate_yearly_report(year, user=None):
        """
        Generate yearly sales report

        Args:
            year: Year
            user: User generating report

        Returns:
            YearlySalesReport instance
        """
        logger.info(f"Generating yearly report for {year}")

        # Get or create report
        report, created = YearlySalesReport.objects.get_or_create(
            year=year,
            defaults={'generated_by': user}
        )

        # Get orders for the year
        orders = Order.objects.filter(
            status='COMPLETED',
            completed_at__year=year
        )

        # Calculate metrics
        aggregates = orders.aggregate(
            total_sales=Sum('total'),
            total_orders=Count('id'),
            avg_order_value=Avg('total'),
            gross_sales=Sum('subtotal'),
            total_discounts=Sum('discount_amount'),
            total_tax=Sum('tax_amount'),
        )


        # Calculate total items from OrderItem
        from apps.orders.models import OrderItem
        total_items = OrderItem.objects.filter(
            order__in=orders
        ).aggregate(total=Sum('quantity'))['total'] or 0

        report.total_sales = aggregates['total_sales'] or 0
        report.total_orders = aggregates['total_orders'] or 0
        report.total_items_sold = total_items
        report.average_order_value = aggregates['avg_order_value'] or 0
        report.gross_sales = aggregates['gross_sales'] or 0
        report.total_discounts = aggregates['total_discounts'] or 0
        report.total_tax = aggregates['total_tax'] or 0
        report.net_sales = report.gross_sales - report.total_discounts
        report.monthly_average_sales = report.total_sales / 12

        # Payment methods
        payments = OrderPayment.objects.filter(
            order__in=orders
        ).values('payment_method').annotate(total=Sum('amount'))

        for payment in payments:
            method = payment['payment_method']
            amount = payment['total'] or 0

            if method == 'CASH':
                report.cash_sales = amount
            elif method == 'CARD':
                report.card_sales = amount
            elif method == 'TRANSFER':
                report.transfer_sales = amount
            elif method == 'MOBILE':
                report.mobile_sales = amount

        # Customer metrics
        customer_orders = orders.exclude(customer__isnull=True)
        report.total_customers = customer_orders.values('customer').distinct().count()

        new_customers = Customer.objects.filter(
            created_at__year=year
        ).count()
        report.new_customers = new_customers

        # Growth (vs previous year)
        try:
            prev_report = YearlySalesReport.objects.get(year=year - 1)

            if prev_report.total_sales > 0:
                report.sales_growth_percentage = (
                        ((report.total_sales - prev_report.total_sales) / prev_report.total_sales) * 100
                )

            if prev_report.total_orders > 0:
                report.order_growth_percentage = (
                        ((report.total_orders - prev_report.total_orders) / prev_report.total_orders) * 100
                )
        except YearlySalesReport.DoesNotExist:
            pass

        # Best month
        best_month = orders.values('completed_at__month').annotate(
            total=Sum('total')
        ).order_by('-total').first()

        if best_month:
            report.best_month = best_month['completed_at__month']
            report.best_month_sales = best_month['total']

        # Monthly breakdown
        monthly_data = []
        for month in range(1, 13):
            month_orders = orders.filter(completed_at__month=month)
            monthly_data.append({
                'month': month,
                'month_name': calendar.month_name[month],
                'sales': float(month_orders.aggregate(total=Sum('total'))['total'] or 0),
                'orders': month_orders.count()
            })

        report.report_data = {
            'monthly_breakdown': monthly_data,
        }

        report.save()

        logger.info(f"Yearly report generated: {year} - ₦{report.total_sales}")

        return report

    @staticmethod
    def _get_hourly_breakdown(report_date):
        """Get hourly sales breakdown for a date"""
        orders = Order.objects.filter(
            status='COMPLETED',
            completed_at__date=report_date
        )

        hourly_data = []
        for hour in range(24):
            hour_orders = orders.filter(completed_at__hour=hour)
            hourly_data.append({
                'hour': hour,
                'time': f"{hour:02d}:00",
                'sales': float(hour_orders.aggregate(total=Sum('total'))['total'] or 0),
                'orders': hour_orders.count()
            })

        return hourly_data

    @staticmethod
    def _get_top_selling_product(start_date, end_date):
        """Get top selling product in period"""
        from apps.orders.models import OrderItem

        top_product = OrderItem.objects.filter(
            order__status='COMPLETED',
            order__completed_at__date__gte=start_date,
            order__completed_at__date__lte=end_date
        ).values(
            'variant__id',
            'variant__product__name'
        ).annotate(
            total_quantity=Sum('quantity')
        ).order_by('-total_quantity').first()

        return top_product