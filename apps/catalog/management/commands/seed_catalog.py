# management/commands/seed_catalog.py
# Place in: apps/catalog/management/commands/seed_catalog.py

from django.core.management.base import BaseCommand
from apps.catalog.models import (
    Category,
    Product,
    VariantAttribute,
    VariantAttributeValue,
    ProductVariant
)


class Command(BaseCommand):
    help = 'Seed catalog with bread products and variants'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding catalog data...')

        # Create Category
        bread_category, created = Category.objects.get_or_create(
            name='Bread',
            defaults={
                'description': 'Fresh baked bread products',
                'is_active': True,
                'display_order': 1
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created category: {bread_category.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠ Category already exists: {bread_category.name}'))

        # Create Size attribute
        size_attr, created = VariantAttribute.objects.get_or_create(
            name='size',
            defaults={
                'display_name': 'Size',
                'display_order': 1
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created attribute: {size_attr.display_name}'))

        # Create size values
        sizes = ['Small', 'Medium', 'Big']
        size_values = {}
        for idx, size in enumerate(sizes):
            size_val, created = VariantAttributeValue.objects.get_or_create(
                attribute=size_attr,
                value=size,
                defaults={'display_order': idx + 1}
            )
            size_values[size] = size_val
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created size: {size}'))

        # Bread products data
        bread_products = [
            {
                'name': 'White Bread',
                'description': 'Classic soft white bread, perfect for sandwiches',
                'base_price': 800,
                'prices': {'Small': 500, 'Medium': 800, 'Big': 1200}
            },
            {
                'name': 'Croissant',
                'description': 'Buttery, flaky French pastry',
                'base_price': 900,
                'prices': {'Small': 600, 'Medium': 900, 'Big': 1300}
            },
            {
                'name': 'Challah',
                'description': 'Traditional braided Jewish bread',
                'base_price': 1000,
                'prices': {'Small': 700, 'Medium': 1000, 'Big': 1400}
            },
            {
                'name': 'Breadstick',
                'description': 'Crispy Italian breadsticks',
                'base_price': 700,
                'prices': {'Small': 400, 'Medium': 700, 'Big': 1000}
            },
            {
                'name': 'Wheat Bread',
                'description': 'Healthy whole wheat bread',
                'base_price': 850,
                'prices': {'Small': 550, 'Medium': 850, 'Big': 1250}
            },
            {
                'name': 'Baguette',
                'description': 'Classic French baguette',
                'base_price': 950,
                'prices': {'Small': 650, 'Medium': 950, 'Big': 1350}
            },
            {
                'name': 'Crispbread',
                'description': 'Light and crunchy Scandinavian crispbread',
                'base_price': 750,
                'prices': {'Small': 450, 'Medium': 750, 'Big': 1050}
            },
            {
                'name': 'Matzah',
                'description': 'Traditional unleavened bread',
                'base_price': 800,
                'prices': {'Small': 500, 'Medium': 800, 'Big': 1100}
            },
        ]

        # Create products and variants
        for product_data in bread_products:
            product, created = Product.objects.get_or_create(
                name=product_data['name'],
                category=bread_category,
                defaults={
                    'description': product_data['description'],
                    'base_price': product_data['base_price'],
                    'is_active': True,
                    'track_inventory': True
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f'✓ Created product: {product.name}'))

                # Create variants for each size
                for size_name, price in product_data['prices'].items():
                    variant = ProductVariant.objects.create(
                        product=product,
                        name=size_name,
                        price=price,
                        cost_price=price * 0.6,  # 40% profit margin
                        stock_quantity=50,
                        low_stock_threshold=10,
                        is_active=True
                    )
                    variant.attribute_values.add(size_values[size_name])
                    self.stdout.write(f'    ✓ Created variant: {size_name} - ₦{price}')
            else:
                self.stdout.write(self.style.WARNING(f'⚠ Product already exists: {product.name}'))

        # Summary
        self.stdout.write(self.style.SUCCESS('\n✓ Catalog seeding completed!'))
        self.stdout.write(f'\nCategories: {Category.objects.count()}')
        self.stdout.write(f'Products: {Product.objects.count()}')
        self.stdout.write(f'Variant Attributes: {VariantAttribute.objects.count()}')
        self.stdout.write(f'Attribute Values: {VariantAttributeValue.objects.count()}')
        self.stdout.write(f'Product Variants: {ProductVariant.objects.count()}')