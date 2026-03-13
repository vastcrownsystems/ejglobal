# apps/reports/management/commands/init_reports.py
"""
Management command to initialize all report templates
Usage: python manage.py init_reports
"""

from django.core.management.base import BaseCommand
from apps.reports.models import ReportTemplate


class Command(BaseCommand):
    help = 'Initialize all report templates in database'

    def handle(self, *args, **kwargs):
        self.stdout.write('Initializing report templates...')

        templates = [
            {
                'name': 'Daily Inventory Report',
                'report_type': 'DAILY_INVENTORY',
                'description': 'Daily stock reconciliation - opening, additions, sales, closing, variance',
                'frequency': 'DAILY',
                'default_format': 'EXCEL',
                'is_active': True
            },
            {
                'name': 'Inventory Movement Report',
                'report_type': 'INVENTORY_MOVEMENT',
                'description': 'Track all stock movements (IN/OUT) for a period',
                'frequency': 'MANUAL',
                'default_format': 'EXCEL',
                'is_active': True
            },
            {
                'name': 'Sales Summary Report',
                'report_type': 'SALES_SUMMARY',
                'description': 'Comprehensive sales analysis with top products, categories, and trends',
                'frequency': 'DAILY',
                'default_format': 'EXCEL',
                'is_active': True
            },
            {
                'name': 'Daily Sales Report',
                'report_type': 'DAILY_SALES',
                'description': 'Daily sales analytics with hourly breakdown',
                'frequency': 'DAILY',
                'default_format': 'EXCEL',
                'is_active': True
            },
            {
                'name': 'Weekly Sales Report',
                'report_type': 'WEEKLY_SALES',
                'description': 'Weekly sales trends and comparisons',
                'frequency': 'WEEKLY',
                'default_format': 'EXCEL',
                'is_active': True
            },
            {
                'name': 'Monthly Sales Report',
                'report_type': 'MONTHLY_SALES',
                'description': 'Monthly sales overview with growth metrics',
                'frequency': 'MONTHLY',
                'default_format': 'EXCEL',
                'is_active': True
            },
            {
                'name': 'Yearly Sales Report',
                'report_type': 'YEARLY_SALES',
                'description': 'Annual performance and trends',
                'frequency': 'YEARLY',
                'default_format': 'EXCEL',
                'is_active': True
            },
            {
                'name': 'Credit Aging Report',
                'report_type': 'CREDIT_AGING',
                'description': 'Outstanding credit balances aged by due date',
                'frequency': 'WEEKLY',
                'default_format': 'EXCEL',
                'is_active': True
            },
            {
                'name': 'Customer Analysis Report',
                'report_type': 'CUSTOMER_ANALYSIS',
                'description': 'Customer purchasing patterns and lifetime value',
                'frequency': 'MONTHLY',
                'default_format': 'EXCEL',
                'is_active': True
            },
            {
                'name': 'Product Performance Report',
                'report_type': 'PRODUCT_PERFORMANCE',
                'description': 'Product sales, profitability, and trends analysis',
                'frequency': 'WEEKLY',
                'default_format': 'EXCEL',
                'is_active': True
            },
            {
                'name': 'Cashier Performance Report',
                'report_type': 'CASHIER_PERFORMANCE',
                'description': 'Sales performance by cashier/user',
                'frequency': 'MANUAL',
                'default_format': 'EXCEL',
                'is_active': True
            },
            {
                'name': 'Profit & Loss Report',
                'report_type': 'PROFIT_LOSS',
                'description': 'Revenue, costs, and profitability analysis',
                'frequency': 'MONTHLY',
                'default_format': 'EXCEL',
                'is_active': True
            },
            {
                'name': 'Low Stock Alert Report',
                'report_type': 'LOW_STOCK_ALERT',
                'description': 'Products below reorder threshold with urgency levels',
                'frequency': 'DAILY',
                'default_format': 'PDF',
                'is_active': True
            },
            {
                'name': 'Overdue Credit Report',
                'report_type': 'OVERDUE_CREDIT',
                'description': 'Credit ledgers past due date',
                'frequency': 'WEEKLY',
                'default_format': 'PDF',
                'is_active': True
            },
        ]

        created_count = 0
        updated_count = 0

        for template_data in templates:
            template, created = ReportTemplate.objects.get_or_create(
                report_type=template_data['report_type'],
                defaults=template_data
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created: {template_data["name"]}')
                )
            else:
                # Update existing template
                for key, value in template_data.items():
                    setattr(template, key, value)
                template.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'⟳ Updated: {template_data["name"]}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Done! Created: {created_count}, Updated: {updated_count}, Total: {len(templates)}'
            )
        )