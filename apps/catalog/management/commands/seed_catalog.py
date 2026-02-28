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
                'name': 'Regular Bread',
                'description': 'Classic soft white bread, perfect for sandwiches',
                'base_price': 1100,
                'prices': {'Small': 300, 'Medium': 500, 'Big': 1100}
            },
            {
                'name': 'Sardine Bread',
                'description': 'Sardine Bread',
                'base_price': 1800,
                'prices': {'Medium': 1000, 'Big': 1800}
            },
            {
                'name': 'Coconut Bread',
                'description': 'Coconut Bread',
                'base_price': 1000,
                'prices': {'Small': 700, 'Medium': 1000, 'Big': 1800}
            },
            {
                'name': 'Wheat Bread',
                'description': 'Healthy whole wheat bread',
                'base_price': 850,
                'prices': {'Small': 550, 'Medium': 850, 'Big': 1250}
            },
            {
                'name': 'Fruit Bread',
                'description': 'Fruit Bread',
                'base_price': 800,
                'prices': {'Small': 500, 'Medium': 800, 'Big': 2000}
            },
            {
                'name': 'Chocolate Bread',
                'description': 'Chocolate Bread',
                'base_price': 800,
                'prices': {'Small': 500, 'Medium': 800, 'Big': 2000}
            },
            {
                'name': 'Cake Bread',
                'description': 'Chocolate Bread',
                'base_price': 800,
                'prices': {'Small': 500, 'Medium': 800, 'Big': 2000}
            },
        ]

        #Create products and variants
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