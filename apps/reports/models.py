# apps/reports/models.py - Reports Models

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

User = get_user_model()


class DailySalesReport(models.Model):
    """
    Daily sales summary report

    Generated automatically at end of day or on-demand
    """

    # Report Info
    report_date = models.DateField(db_index=True, unique=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='daily_reports_generated'
    )

    # Sales Metrics
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)
    total_items_sold = models.PositiveIntegerField(default=0)
    average_order_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Revenue Breakdown
    gross_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_discounts = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Payment Methods
    cash_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    card_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    transfer_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mobile_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Customer Metrics
    total_customers = models.PositiveIntegerField(default=0)
    new_customers = models.PositiveIntegerField(default=0)
    returning_customers = models.PositiveIntegerField(default=0)
    walk_in_sales = models.PositiveIntegerField(default=0)

    # Order Status
    completed_orders = models.PositiveIntegerField(default=0)
    cancelled_orders = models.PositiveIntegerField(default=0)
    refunded_orders = models.PositiveIntegerField(default=0)

    # Operational Metrics
    sessions_count = models.PositiveIntegerField(default=0)
    unique_cashiers = models.PositiveIntegerField(default=0)

    # Top Performers
    top_selling_product_id = models.IntegerField(null=True, blank=True)
    top_selling_product_name = models.CharField(max_length=200, blank=True)
    top_selling_product_quantity = models.PositiveIntegerField(default=0)

    # Report Data (JSON for detailed breakdown)
    report_data = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'daily_sales_reports'
        ordering = ['-report_date']
        indexes = [
            models.Index(fields=['-report_date']),
        ]

    def __str__(self):
        return f"Daily Report - {self.report_date}"

    @property
    def discount_percentage(self):
        """Calculate discount as percentage of gross sales"""
        if self.gross_sales > 0:
            return (self.total_discounts / self.gross_sales) * 100
        return 0


class WeeklySalesReport(models.Model):
    """
    Weekly sales summary report
    """

    # Report Info
    year = models.PositiveIntegerField()
    week_number = models.PositiveIntegerField()  # 1-52
    week_start_date = models.DateField()
    week_end_date = models.DateField()
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='weekly_reports_generated'
    )

    # Sales Metrics
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)
    total_items_sold = models.PositiveIntegerField(default=0)
    average_order_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    daily_average_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Revenue Breakdown
    gross_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_discounts = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Payment Methods
    cash_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    card_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    transfer_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mobile_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Customer Metrics
    total_customers = models.PositiveIntegerField(default=0)
    new_customers = models.PositiveIntegerField(default=0)

    # Growth Metrics
    sales_growth_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    order_growth_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Report Data
    report_data = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'weekly_sales_reports'
        ordering = ['-year', '-week_number']
        unique_together = ['year', 'week_number']
        indexes = [
            models.Index(fields=['-year', '-week_number']),
        ]

    def __str__(self):
        return f"Week {self.week_number}, {self.year}"


class MonthlySalesReport(models.Model):
    """
    Monthly sales summary report
    """

    # Report Info
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()  # 1-12
    month_name = models.CharField(max_length=20)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='monthly_reports_generated'
    )

    # Sales Metrics
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)
    total_items_sold = models.PositiveIntegerField(default=0)
    average_order_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    daily_average_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Revenue Breakdown
    gross_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_discounts = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Payment Methods
    cash_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    card_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    transfer_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mobile_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Customer Metrics
    total_customers = models.PositiveIntegerField(default=0)
    new_customers = models.PositiveIntegerField(default=0)
    customer_retention_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Growth Metrics
    sales_growth_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    order_growth_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Best Day
    best_sales_day = models.DateField(null=True, blank=True)
    best_sales_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Report Data
    report_data = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'monthly_sales_reports'
        ordering = ['-year', '-month']
        unique_together = ['year', 'month']
        indexes = [
            models.Index(fields=['-year', '-month']),
        ]

    def __str__(self):
        return f"{self.month_name} {self.year}"


class YearlySalesReport(models.Model):
    """
    Yearly sales summary report
    """

    # Report Info
    year = models.PositiveIntegerField(unique=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='yearly_reports_generated'
    )

    # Sales Metrics
    total_sales = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)
    total_items_sold = models.PositiveIntegerField(default=0)
    average_order_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monthly_average_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Revenue Breakdown
    gross_sales = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_discounts = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_sales = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Payment Methods
    cash_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    card_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    transfer_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mobile_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Customer Metrics
    total_customers = models.PositiveIntegerField(default=0)
    new_customers = models.PositiveIntegerField(default=0)
    customer_retention_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Growth Metrics
    sales_growth_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    order_growth_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Best Performers
    best_month = models.PositiveIntegerField(null=True, blank=True)
    best_month_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Report Data (Monthly breakdown)
    report_data = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'yearly_sales_reports'
        ordering = ['-year']
        indexes = [
            models.Index(fields=['-year']),
        ]

    def __str__(self):
        return f"Annual Report {self.year}"


class ProductPerformanceReport(models.Model):
    """
    Product performance tracking
    """

    # Report Period
    report_type = models.CharField(
        max_length=20,
        choices=[
            ('DAILY', 'Daily'),
            ('WEEKLY', 'Weekly'),
            ('MONTHLY', 'Monthly'),
            ('YEARLY', 'Yearly'),
        ]
    )
    period_start = models.DateField()
    period_end = models.DateField()

    # Product Info
    product_id = models.IntegerField()
    product_name = models.CharField(max_length=200)
    variant_id = models.IntegerField(null=True, blank=True)
    variant_name = models.CharField(max_length=200, blank=True)
    sku = models.CharField(max_length=100, blank=True)

    # Performance Metrics
    units_sold = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    average_selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Rankings
    revenue_rank = models.PositiveIntegerField(null=True, blank=True)
    quantity_rank = models.PositiveIntegerField(null=True, blank=True)

    # Timestamps
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'product_performance_reports'
        ordering = ['-period_end', '-total_revenue']
        indexes = [
            models.Index(fields=['-period_end', 'report_type']),
            models.Index(fields=['product_id']),
        ]

    def __str__(self):
        return f"{self.product_name} - {self.report_type} ({self.period_end})"