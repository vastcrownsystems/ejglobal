from django.core.management.base import BaseCommand
from django.db.models import Sum
from apps.customers.models import Customer
from apps.orders.models import Order


class Command(BaseCommand):
    help = 'Update customer statistics'

    def handle(self, *args, **options):
        customers = Customer.objects.filter(is_active=True)
        total = customers.count()

        self.stdout.write(f'Updating {total} customers...')

        for i, customer in enumerate(customers, 1):
            orders = Order.objects.filter(
                customer=customer,
                status='COMPLETED'
            )

            customer.total_orders = orders.count()
            customer.total_spent = orders.aggregate(
                total=Sum('total')
            )['total'] or 0

            last_order = orders.order_by('-completed_at').first()
            customer.last_purchase_date = last_order.completed_at if last_order else None

            customer.save(update_fields=[
                'total_orders',
                'total_spent',
                'last_purchase_date'
            ])

            if i % 10 == 0:
                self.stdout.write(f'  Progress: {i}/{total}')

        self.stdout.write(
            self.style.SUCCESS(f'✅ Updated {total} customers')
        )