# management/commands/seed_sales.py
# Place in: apps/sales/management/commands/seed_sales.py

from django.core.management.base import BaseCommand
from apps.sales.models import Store, Register


class Command(BaseCommand):
    help = 'Seed initial store and register data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding sales data...')

        # Create default store
        store, created = Store.objects.get_or_create(
            name='Main Store',
            defaults={
                'address': '123 Main Street, Lagos, Nigeria',
                'is_active': True
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created store: {store.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠ Store already exists: {store.name}'))

        # Create default register
        register, created = Register.objects.get_or_create(
            store=store,
            code='REG-001',
            defaults={
                'name': 'ejglobal station 1',
                'is_active': True
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created register: {register.name} ({register.code})'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠ Register already exists: {register.name} ({register.code})'))

        self.stdout.write(self.style.SUCCESS('\n✓ Sales data seeding completed!'))
        self.stdout.write(f'\nStores: {Store.objects.count()}')
        self.stdout.write(f'Registers: {Register.objects.count()}')