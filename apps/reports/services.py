# apps/reports/services.py - Comprehensive Reporting Service

from django.db import transaction
from django.db.models import Sum, Count, Avg, Q, F, Max, Min, Case, When, Value, CharField
from django.utils import timezone
from datetime import datetime, timedelta, date
from decimal import Decimal
import calendar
import logging
from django.db.models.functions import TruncDate, ExtractHour
from django.db.models import ExpressionWrapper, DecimalField

from .models import (
    DailySalesReport,
    WeeklySalesReport,
    MonthlySalesReport,
    YearlySalesReport,
    ProductPerformanceReport
)
from apps.orders.models import Order, OrderItem, OrderPayment
from apps.customers.models import Customer
from apps.catalog.models import Product, ProductVariant

logger = logging.getLogger(__name__)


class ReportService:
    """
    Comprehensive reporting service with flexible date ranges and analytics

    Features:
    - Daily, Weekly, Monthly, Yearly, Custom period reports
    - Product performance tracking (individual products and variants)
    - Revenue analysis with breakdowns
    - Payment method analysis
    - Customer analytics
    - Growth metrics and comparisons
    """

    # ============================================
    # CORE ANALYTICS ENGINE
    # ============================================

    @staticmethod
    def get_sales_analytics(start_date, end_date):
        """
        Core analytics engine - returns comprehensive sales data for any period

        Args:
            start_date: Period start date
            end_date: Period end date

        Returns:
            dict: Complete sales analytics
        """
        # Get completed orders in period
        orders = Order.objects.filter(
            status='COMPLETED',
            completed_at__date__gte=start_date,
            completed_at__date__lte=end_date
        )

        # Basic metrics
        total_orders = orders.count()

        # Sales metrics
        items = OrderItem.objects.filter(order__in=orders)

        sales_data = orders.aggregate(
            total_sales=Sum('total'),
            gross_sales=Sum('subtotal'),
            total_tax=Sum('tax_amount'),
            total_discounts=Sum('discount_amount'),
            average_order_value=Avg('total')
        )

        total_items = items.aggregate(
            total=Sum('quantity')
        )['total'] or 0



        # Net sales calculation
        net_sales = (
                (sales_data['gross_sales'] or Decimal('0.00'))
                - (sales_data['total_discounts'] or Decimal('0.00'))
        )

        # Payment method breakdown
        payment_breakdown = OrderPayment.objects.filter(
            order__in=orders
        ).values('payment_method').annotate(
            total=Sum('amount'),
            count=Count('id')
        )

        cash_sales = sum(p['total'] for p in payment_breakdown if p['payment_method'] == 'CASH')
        card_sales = sum(p['total'] for p in payment_breakdown if p['payment_method'] == 'CARD')
        transfer_sales = sum(p['total'] for p in payment_breakdown if p['payment_method'] == 'TRANSFER')

        # Customer metrics
        customer_data = orders.exclude(customer__isnull=True) \
            .values('customer') \
            .distinct() \
            .count()
        walk_in_orders = orders.filter(customer__isnull=True).count()

        # Get new vs returning customers in period
        customer_ids = orders.filter(customer__isnull=False).values_list('customer', flat=True).distinct()
        new_customers = Customer.objects.filter(
            id__in=customer_ids,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).count()

        returning_customers = len(customer_ids) - new_customers

        # Order status breakdown
        completed_count = orders.filter(status='COMPLETED').count()
        cancelled_count = Order.objects.filter(
            status='CANCELLED',
            updated_at__date__gte=start_date,
            updated_at__date__lte=end_date
        ).count()
        refunded_count = Order.objects.filter(
            status='REFUNDED',
            updated_at__date__gte=start_date,
            updated_at__date__lte=end_date
        ).count()

        # Top-selling product
        top_product = OrderItem.objects.filter(
            order__in=orders
        ).values(
            'variant',
            'product_name',
            'variant_name'
        ).annotate(
            total_quantity=Sum('quantity')
        ).order_by('-total_quantity').first()

        return {
            # Basic metrics
            'total_orders': total_orders,
            'total_items_sold': total_items,

            # Revenue metrics
            'total_sales': sales_data['total_sales'] or Decimal('0.00'),
            'gross_sales': sales_data['gross_sales'] or Decimal('0.00'),
            'net_sales': net_sales,
            'total_tax': sales_data['total_tax'] or Decimal('0.00'),
            'total_discounts': sales_data['total_discounts'] or Decimal('0.00'),
            'average_order_value': sales_data['average_order_value'] or Decimal('0.00'),

            # Payment methods
            'cash_sales': cash_sales,
            'card_sales': card_sales,
            'transfer_sales': transfer_sales,
            'payment_breakdown': list(payment_breakdown),

            # Customer metrics
            'total_customers': customer_data,
            'new_customers': new_customers,
            'returning_customers': returning_customers,
            'walk_in_sales': walk_in_orders,

            # Order status
            'completed_orders': completed_count,
            'cancelled_orders': cancelled_count,
            'refunded_orders': refunded_count,

            # Top performers
            'top_product': top_product,

            # Period info
            'period_start': start_date,
            'period_end': end_date,
            'period_days': (end_date - start_date).days + 1,
        }

    @staticmethod
    def get_product_performance(start_date, end_date, product_id=None, variant_id=None):
        """
        Get product/variant performance for a period

        Args:
            start_date: Period start
            end_date: Period end
            product_id: Optional specific product ID
            variant_id: Optional specific variant ID

        Returns:
            QuerySet or dict of product performance data
        """
        orders = Order.objects.filter(
            status='COMPLETED',
            completed_at__date__gte=start_date,
            completed_at__date__lte=end_date
        )

        items = OrderItem.objects.filter(order__in=orders)

        revenue = ExpressionWrapper(
            F('quantity') * F('unit_price'),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )

        # Filter by product/variant if specified
        if product_id:
            items = items.filter(product_id=product_id)
        if variant_id:
            items = items.filter(variant_id=variant_id)


        # Aggregate by product (and variant if exists)
        if variant_id or not product_id:
            # Group by both product and variant
            performance = items.values(
                'product_id',
                'product__name',
                'variant_id',
                'variant__name',
                'variant__sku'
            ).annotate(
                units_sold=Sum('quantity'),
                total_revenue=Sum(revenue),
                total_discount=Sum('discount_amount'),
                average_price=Avg('unit_price'),
                order_count=Count('order', distinct=True)
            ).order_by('-total_revenue')
        else:
            # Group by product only
            performance = items.filter(
                product_id=product_id
            ).aggregate(
                units_sold=Sum('quantity'),
                total_revenue=Sum(revenue),
                total_discount=Sum('discount_amount'),
                average_price=Avg('unit_price'),
                order_count=Count('order', distinct=True)
            )

        return performance

    @staticmethod
    def get_daily_breakdown(start_date, end_date):
        """
        Get day-by-day breakdown for a period

        Returns:
            list: Daily sales data
        """
        orders = Order.objects.filter(
            status='COMPLETED',
            completed_at__date__gte=start_date,
            completed_at__date__lte=end_date
        )

        daily_data = orders.annotate(
            day=TruncDate('completed_at')
        ).values('day').annotate(
            total_sales=Sum('total'),
            total_orders=Count('id'),
            total_items=Sum('items__quantity'),
            average_order=Avg('total')
        ).order_by('day')

        return list(daily_data)

    @staticmethod
    def get_hourly_breakdown(report_date):
        """
        Get hour-by-hour breakdown for a single day

        Returns:
            list: Hourly sales data
        """
        orders = Order.objects.filter(
            status='COMPLETED',
            completed_at__date=report_date
        )

        hourly_data = orders.extra(
            orders.annotate(
                hour=ExtractHour('completed_at')
            )
        ).values('hour').annotate(
            total_sales=Sum('total'),
            total_orders=Count('id'),
            total_items=Sum('total_quantity')
        ).order_by('hour')

        return list(hourly_data)

    @staticmethod
    def get_category_performance(start_date, end_date):
        """
        Get sales performance by product category

        Returns:
            QuerySet: Category performance data
        """
        orders = Order.objects.filter(
            status='COMPLETED',
            completed_at__date__gte=start_date,
            completed_at__date__lte=end_date
        )

        category_data = OrderItem.objects.filter(
            order__in=orders
        ).values(
            'product__category__id',
            'product__category__name'
        ).annotate(
            total_revenue=Sum(F('quantity') * F('unit_price')),
            units_sold=Sum('quantity'),
            product_count=Count('product', distinct=True)
        ).order_by('-total_revenue')

        return category_data

    @staticmethod
    def compare_periods(current_start, current_end, previous_start, previous_end):
        """
        Compare two periods and calculate growth metrics

        Returns:
            dict: Comparison metrics with growth percentages
        """
        current = ReportService.get_sales_analytics(current_start, current_end)
        previous = ReportService.get_sales_analytics(previous_start, previous_end)

        def calculate_growth(current_val, previous_val):
            """Calculate percentage growth"""
            if previous_val == 0:
                return 100 if current_val > 0 else 0
            return ((current_val - previous_val) / previous_val) * 100

        return {
            'current_period': current,
            'previous_period': previous,
            'growth': {
                'sales_growth': calculate_growth(
                    current['total_sales'],
                    previous['total_sales']
                ),
                'orders_growth': calculate_growth(
                    current['total_orders'],
                    previous['total_orders']
                ),
                'customers_growth': calculate_growth(
                    current['total_customers'],
                    previous['total_customers']
                ),
                'aov_growth': calculate_growth(
                    current['average_order_value'],
                    previous['average_order_value']
                ),
            }
        }

    # ============================================
    # DAILY REPORTS
    # ============================================

    @staticmethod
    @transaction.atomic
    def generate_daily_report(report_date=None, user=None):
        """
        Generate comprehensive daily sales report

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

        # Get analytics
        analytics = ReportService.get_sales_analytics(report_date, report_date)

        # Get hourly breakdown
        hourly = ReportService.get_hourly_breakdown(report_date)

        # Get category performance
        categories = list(ReportService.get_category_performance(report_date, report_date))

        # Update report
        report.total_sales = analytics['total_sales']
        report.total_orders = analytics['total_orders']
        report.total_items_sold = analytics['total_items_sold']
        report.average_order_value = analytics['average_order_value']

        report.gross_sales = analytics['gross_sales']
        report.total_discounts = analytics['total_discounts']
        report.total_tax = analytics['total_tax']
        report.net_sales = analytics['net_sales']

        report.cash_sales = analytics['cash_sales']
        report.card_sales = analytics['card_sales']
        report.transfer_sales = analytics['transfer_sales']

        report.total_customers = analytics['total_customers']
        report.new_customers = analytics['new_customers']
        report.returning_customers = analytics['returning_customers']
        report.walk_in_sales = analytics['walk_in_sales']

        report.completed_orders = analytics['completed_orders']
        report.cancelled_orders = analytics['cancelled_orders']
        report.refunded_orders = analytics['refunded_orders']

        if analytics['top_product']:
            report.top_selling_product_id = analytics['top_product']['product_id']
            report.top_selling_product_name = analytics['top_product']['product__name']
            report.top_selling_product_quantity = analytics['top_product']['total_quantity']

        # Store additional data
        report.report_data = {
            'hourly_breakdown': hourly,
            'category_performance': categories,
            'payment_breakdown': analytics['payment_breakdown'],
        }

        report.save()

        logger.info(f"Daily report generated: ₦{analytics['total_sales']}")

        return report

    @staticmethod
    def get_daily_report(report_date):
        """Get or generate daily report"""
        try:
            return DailySalesReport.objects.get(report_date=report_date)
        except DailySalesReport.DoesNotExist:
            return ReportService.generate_daily_report(report_date)

    # ============================================
    # CUSTOM PERIOD REPORTS
    # ============================================

    @staticmethod
    def generate_custom_report(start_date, end_date, include_comparisons=True):
        """
        Generate custom period report with comprehensive analytics

        Args:
            start_date: Period start date
            end_date: Period end date
            include_comparisons: Include previous period comparison

        Returns:
            dict: Complete report data
        """
        logger.info(f"Generating custom report: {start_date} to {end_date}")

        # Get main analytics
        analytics = ReportService.get_sales_analytics(start_date, end_date)

        # Get daily breakdown
        daily = ReportService.get_daily_breakdown(start_date, end_date)

        # Get product performance
        products = list(ReportService.get_product_performance(start_date, end_date))

        # Get category performance
        categories = list(ReportService.get_category_performance(start_date, end_date))

        # Calculate averages
        period_days = analytics['period_days']
        daily_average_sales = analytics['total_sales'] / period_days if period_days > 0 else 0
        daily_average_orders = analytics['total_orders'] / period_days if period_days > 0 else 0

        report = {
            **analytics,
            'daily_average_sales': daily_average_sales,
            'daily_average_orders': daily_average_orders,
            'daily_breakdown': daily,
            'product_performance': products[:20],  # Top 20
            'category_performance': categories,
        }

        # Add period comparison if requested
        if include_comparisons:
            period_length = (end_date - start_date).days + 1
            prev_end = start_date - timedelta(days=1)
            prev_start = prev_end - timedelta(days=period_length - 1)

            comparison = ReportService.compare_periods(
                start_date, end_date,
                prev_start, prev_end
            )
            report['comparison'] = comparison

        return report

    # ============================================
    # MONTHLY REPORTS
    # ============================================

    @staticmethod
    @transaction.atomic
    def generate_monthly_report(year, month, user=None):
        """
        Generate monthly sales report

        Args:
            year: Report year
            month: Report month (1-12)
            user: User generating report

        Returns:
            MonthlySalesReport instance
        """
        logger.info(f"Generating monthly report for {month}/{year}")

        # Get or create report
        report, created = MonthlySalesReport.objects.get_or_create(
            year=year,
            month=month,
            defaults={
                'generated_by': user,
                'month_name': calendar.month_name[month]
            }
        )

        # Calculate period
        start_date = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, last_day)

        # Get analytics
        analytics = ReportService.get_sales_analytics(start_date, end_date)

        # Get daily breakdown
        daily = ReportService.get_daily_breakdown(start_date, end_date)

        # Find best sales day
        best_day = max(daily, key=lambda x: x['total_sales']) if daily else None

        # Calculate growth vs previous month
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1

        prev_start = date(prev_year, prev_month, 1)
        prev_last_day = calendar.monthrange(prev_year, prev_month)[1]
        prev_end = date(prev_year, prev_month, prev_last_day)

        comparison = ReportService.compare_periods(
            start_date, end_date,
            prev_start, prev_end
        )

        # Update report
        days_in_month = last_day

        report.total_sales = analytics['total_sales']
        report.total_orders = analytics['total_orders']
        report.total_items_sold = analytics['total_items_sold']
        report.average_order_value = analytics['average_order_value']
        report.daily_average_sales = analytics['total_sales'] / days_in_month

        report.gross_sales = analytics['gross_sales']
        report.total_discounts = analytics['total_discounts']
        report.total_tax = analytics['total_tax']
        report.net_sales = analytics['net_sales']

        report.cash_sales = analytics['cash_sales']
        report.card_sales = analytics['card_sales']
        report.transfer_sales = analytics['transfer_sales']

        report.total_customers = analytics['total_customers']
        report.new_customers = analytics['new_customers']

        report.sales_growth_percentage = comparison['growth']['sales_growth']
        report.order_growth_percentage = comparison['growth']['orders_growth']

        if best_day:
            report.best_sales_day = best_day['day']
            report.best_sales_amount = best_day['total_sales']

        # Store additional data
        report.report_data = {
            'daily_breakdown': daily,
            'comparison_data': comparison,
        }

        report.save()

        logger.info(f"Monthly report generated: ₦{analytics['total_sales']}")

        return report

    @staticmethod
    def get_monthly_report(year, month):
        """Get or generate monthly report"""
        try:
            return MonthlySalesReport.objects.get(year=year, month=month)
        except MonthlySalesReport.DoesNotExist:
            return ReportService.generate_monthly_report(year, month)

    # ============================================
    # YEARLY REPORTS
    # ============================================

    @staticmethod
    @transaction.atomic
    def generate_yearly_report(year, user=None):
        """
        Generate yearly sales report

        Args:
            year: Report year
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

        # Calculate period
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        # Get analytics
        analytics = ReportService.get_sales_analytics(start_date, end_date)

        # Get monthly breakdown
        monthly_data = []
        best_month = None
        best_month_sales = Decimal('0.00')

        for month in range(1, 13):
            month_start = date(year, month, 1)
            month_end = date(year, month, calendar.monthrange(year, month)[1])
            month_analytics = ReportService.get_sales_analytics(month_start, month_end)

            monthly_data.append({
                'month': month,
                'month_name': calendar.month_name[month],
                'sales': month_analytics['total_sales'],
                'orders': month_analytics['total_orders'],
            })

            if month_analytics['total_sales'] > best_month_sales:
                best_month = month
                best_month_sales = month_analytics['total_sales']

        # Calculate growth vs previous year
        prev_start = date(year - 1, 1, 1)
        prev_end = date(year - 1, 12, 31)

        comparison = ReportService.compare_periods(
            start_date, end_date,
            prev_start, prev_end
        )

        # Update report
        report.total_sales = analytics['total_sales']
        report.total_orders = analytics['total_orders']
        report.total_items_sold = analytics['total_items_sold']
        report.average_order_value = analytics['average_order_value']
        report.monthly_average_sales = analytics['total_sales'] / 12

        report.gross_sales = analytics['gross_sales']
        report.total_discounts = analytics['total_discounts']
        report.total_tax = analytics['total_tax']
        report.net_sales = analytics['net_sales']

        report.cash_sales = analytics['cash_sales']
        report.card_sales = analytics['card_sales']
        report.transfer_sales = analytics['transfer_sales']

        report.total_customers = analytics['total_customers']
        report.new_customers = analytics['new_customers']

        report.sales_growth_percentage = comparison['growth']['sales_growth']
        report.order_growth_percentage = comparison['growth']['orders_growth']

        report.best_month = best_month
        report.best_month_sales = best_month_sales

        # Store additional data
        report.report_data = {
            'monthly_breakdown': monthly_data,
            'comparison_data': comparison,
        }

        report.save()

        logger.info(f"Yearly report generated: ₦{analytics['total_sales']}")

        return report

    @staticmethod
    def get_yearly_report(year):
        """Get or generate yearly report"""
        try:
            return YearlySalesReport.objects.get(year=year)
        except YearlySalesReport.DoesNotExist:
            return ReportService.generate_yearly_report(year)


# ============================================
# QUICK ACCESS FUNCTIONS
# ============================================

def get_today_sales():
    """Get today's sales summary"""
    today = timezone.now().date()
    return ReportService.get_sales_analytics(today, today)


def get_week_sales():
    """Get this week's sales"""
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    return ReportService.get_sales_analytics(week_start, today)


def get_month_sales():
    """Get this month's sales"""
    today = timezone.now().date()
    month_start = today.replace(day=1)
    return ReportService.get_sales_analytics(month_start, today)


def get_year_sales():
    """Get this year's sales"""
    today = timezone.now().date()
    year_start = today.replace(month=1, day=1)
    return ReportService.get_sales_analytics(year_start, today)