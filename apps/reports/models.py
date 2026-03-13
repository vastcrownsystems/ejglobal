# apps/reports/models.py - COMPLETE MODELS (All Included)
"""
Professional Reporting System Models
Complete integration with sales analytics and inventory reconciliation
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

User = get_user_model()


# ============================================
# REPORT TEMPLATES & GENERATION
# ============================================

class ReportTemplate(models.Model):
    """Predefined report templates with configurations"""
    REPORT_TYPES = [
        ('DAILY_INVENTORY', 'Daily Inventory Report'),
        ('INVENTORY_MOVEMENT', 'Inventory Movement Report'),
        ('SALES_SUMMARY', 'Sales Summary Report'),
        ('DAILY_SALES', 'Daily Sales Report'),
        ('WEEKLY_SALES', 'Weekly Sales Report'),
        ('MONTHLY_SALES', 'Monthly Sales Report'),
        ('YEARLY_SALES', 'Yearly Sales Report'),
        ('CREDIT_AGING', 'Credit Aging Report'),
        ('CUSTOMER_ANALYSIS', 'Customer Analysis Report'),
        ('PRODUCT_PERFORMANCE', 'Product Performance Report'),
        ('CASHIER_PERFORMANCE', 'Cashier Performance Report'),
        ('PROFIT_LOSS', 'Profit & Loss Report'),
        ('LOW_STOCK_ALERT', 'Low Stock Alert Report'),
        ('OVERDUE_CREDIT', 'Overdue Credit Report'),
    ]

    FREQUENCY_CHOICES = [
        ('MANUAL', 'Manual Only'),
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
    ]

    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES, unique=True)
    description = models.TextField()
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='MANUAL')
    schedule_time = models.TimeField(null=True, blank=True, help_text='Time to generate report')
    default_format = models.CharField(
        max_length=10,
        choices=[('EXCEL', 'Excel'), ('PDF', 'PDF')],
        default='EXCEL'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'report_templates'
        ordering = ['name']

    def __str__(self):
        return self.name


class GeneratedReport(models.Model):
    """Audit trail of all generated reports"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    report_template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE, related_name='generated_reports')
    report_number = models.CharField(max_length=50, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    date_from = models.DateField()
    date_to = models.DateField()
    file_format = models.CharField(max_length=10)
    file_path = models.FileField(upload_to='reports/%Y/%m/', null=True, blank=True)
    file_size = models.IntegerField(null=True, blank=True, help_text='File size in bytes')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    error_message = models.TextField(blank=True)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='generated_reports')
    generated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    row_count = models.IntegerField(default=0, help_text='Number of data rows')
    processing_time = models.FloatField(null=True, blank=True, help_text='Processing time in seconds')
    filters_applied = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'generated_reports'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['-generated_at']),
            models.Index(fields=['report_template', '-generated_at']),
            models.Index(fields=['generated_by', '-generated_at']),
        ]

    def __str__(self):
        return f"{self.report_number} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.report_number:
            self.report_number = self.generate_report_number()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_report_number():
        """Generate unique report number"""
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        import random
        suffix = random.randint(100, 999)
        return f'RPT-{timestamp}-{suffix}'


class ReportSchedule(models.Model):
    """Scheduled report generation"""
    report_template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE, related_name='schedules')
    recipients = models.ManyToManyField(User, related_name='scheduled_reports',
                                        help_text='Users who will receive the report')
    additional_emails = models.TextField(blank=True, help_text='Additional email addresses (comma-separated)')
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_schedules')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'report_schedules'
        ordering = ['next_run']

    def __str__(self):
        return f"{self.report_template.name} - {self.report_template.frequency}"


# ============================================
# SALES ANALYTICS REPORTS (Cached)
# ============================================

class DailySalesReport(models.Model):
    """Daily sales summary report (cached analytics)"""
    report_date = models.DateField(db_index=True, unique=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                     related_name='daily_sales_reports_generated')

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

    # Top Performers
    top_selling_product_id = models.IntegerField(null=True, blank=True)
    top_selling_product_name = models.CharField(max_length=200, blank=True)
    top_selling_product_quantity = models.PositiveIntegerField(default=0)

    # Report Data (JSON)
    report_data = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'daily_sales_reports'
        ordering = ['-report_date']
        indexes = [models.Index(fields=['-report_date'])]

    def __str__(self):
        return f"Daily Sales - {self.report_date}"

    @property
    def discount_percentage(self):
        if self.gross_sales > 0:
            return (self.total_discounts / self.gross_sales) * 100
        return 0


class WeeklySalesReport(models.Model):
    """Weekly sales summary report"""
    year = models.PositiveIntegerField()
    week_number = models.PositiveIntegerField()  # 1-52
    week_start_date = models.DateField()
    week_end_date = models.DateField()
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                     related_name='weekly_reports_generated')

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

    report_data = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'weekly_sales_reports'
        ordering = ['-year', '-week_number']
        unique_together = ['year', 'week_number']
        indexes = [models.Index(fields=['-year', '-week_number'])]

    def __str__(self):
        return f"Week {self.week_number}, {self.year}"


class MonthlySalesReport(models.Model):
    """Monthly sales summary report"""
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()  # 1-12
    month_name = models.CharField(max_length=20)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                     related_name='monthly_sales_reports_generated')

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

    report_data = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'monthly_sales_reports'
        ordering = ['-year', '-month']
        unique_together = ['year', 'month']
        indexes = [models.Index(fields=['-year', '-month'])]

    def __str__(self):
        return f"{self.month_name} {self.year}"


class YearlySalesReport(models.Model):
    """Yearly sales summary report"""
    year = models.PositiveIntegerField(unique=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                     related_name='yearly_reports_generated')

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

    report_data = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'yearly_sales_reports'
        ordering = ['-year']
        indexes = [models.Index(fields=['-year'])]

    def __str__(self):
        return f"Annual Report {self.year}"


class ProductPerformanceReport(models.Model):
    """Product performance tracking"""
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


# ============================================
# INVENTORY RECONCILIATION REPORTS
# ============================================

class DailyInventoryReport(models.Model):
    """Daily inventory reconciliation - tracks stock from opening to closing"""
    report_date = models.DateField(db_index=True)
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE, related_name='daily_inventory_reports')
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.CASCADE, null=True, blank=True,
                                related_name='daily_inventory_reports')

    # Stock Levels
    opening_stock = models.IntegerField(default=0, help_text='Stock at start of day')
    stock_added = models.IntegerField(default=0, help_text='Stock added (production/purchase)')
    stock_removed = models.IntegerField(default=0, help_text='Stock removed (wastage/damage)')
    quantity_sold = models.IntegerField(default=0, help_text='Quantity sold')
    expected_closing = models.IntegerField(default=0, help_text='Expected closing stock')
    actual_closing = models.IntegerField(default=0, help_text='Actual closing stock')
    variance = models.IntegerField(default=0, help_text='Difference (shrinkage/overage)')

    # Financial
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Sales revenue')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_value = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Value of closing stock')

    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'daily_inventory_reports'
        ordering = ['-report_date', 'product__name']
        unique_together = ['report_date', 'product', 'variant']
        indexes = [
            models.Index(fields=['-report_date']),
            models.Index(fields=['product', '-report_date']),
        ]

    def __str__(self):
        if self.variant:
            return f"{self.product.name} - {self.variant.name} ({self.report_date})"
        return f"{self.product.name} ({self.report_date})"

    @property
    def variance_percentage(self):
        if self.opening_stock > 0:
            return (self.variance / self.opening_stock) * 100
        return 0

    @property
    def stock_status(self):
        if self.actual_closing <= 0:
            return 'OUT_OF_STOCK'
        elif self.actual_closing <= 10:
            return 'LOW_STOCK'
        elif self.actual_closing <= 50:
            return 'NORMAL'
        return 'HIGH_STOCK'

    @property
    def has_variance(self):
        return self.variance != 0

    @property
    def is_shrinkage(self):
        return self.variance < 0

    @property
    def is_overage(self):
        return self.variance > 0