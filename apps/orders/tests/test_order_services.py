# apps/orders/tests/test_order_services.py
"""
Tests for Order Services
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from decimal import Decimal

from apps.orders.models import Order, OrderItem
from apps.orders.services import OrderService
from apps.catalog.models import Category, Product, ProductVariant

User = get_user_model()


class OrderServiceTestCase(TestCase):
    """Test Order Service methods"""

    def setUp(self):
        """Set up test data"""
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        # Create category
        self.category = Category.objects.create(
            name='Bread',
            slug='bread'
        )

        # Create products
        self.product1 = Product.objects.create(
            name='White Bread',
            slug='white-bread',
            sku='SKU-BREAD001',
            category=self.category,
            base_price=Decimal('500.00'),
            is_active=True,
            track_inventory=True
        )

        self.product2 = Product.objects.create(
            name='Croissant',
            slug='croissant',
            sku='SKU-CROIS001',
            category=self.category,
            base_price=Decimal('600.00'),
            is_active=True,
            track_inventory=True
        )

        # Create variants
        self.variant1 = ProductVariant.objects.create(
            product=self.product1,
            sku='SKU-BREAD001-001',
            price=Decimal('500.00'),
            cost_price=Decimal('300.00'),
            stock_quantity=100,
            is_active=True
        )

        self.variant2 = ProductVariant.objects.create(
            product=self.product2,
            sku='SKU-CROIS001-001',
            price=Decimal('600.00'),
            cost_price=Decimal('400.00'),
            stock_quantity=50,
            is_active=True
        )

    def test_create_draft_order(self):
        """Test creating a draft order"""
        order = OrderService.create_draft_order(
            user=self.user,
            customer_name='John Doe',
            customer_email='john@example.com'
        )

        self.assertEqual(order.status, 'DRAFT')
        self.assertEqual(order.customer_name, 'John Doe')
        self.assertEqual(order.created_by, self.user)
        self.assertEqual(order.subtotal, Decimal('0.00'))
        self.assertEqual(order.total, Decimal('0.00'))
        self.assertTrue(order.order_number.startswith('ORD-'))

    def test_add_item_to_order(self):
        """Test adding item to order"""
        order = OrderService.create_draft_order(user=self.user)

        item = OrderService.add_item(
            order=order,
            variant_id=self.variant1.id,
            quantity=2
        )

        self.assertEqual(item.variant, self.variant1)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, Decimal('500.00'))
        self.assertEqual(item.line_total, Decimal('1000.00'))

        # Check order totals updated
        order.refresh_from_db()
        self.assertEqual(order.subtotal, Decimal('1000.00'))
        self.assertEqual(order.total, Decimal('1000.00'))

    def test_add_multiple_items(self):
        """Test adding multiple different items"""
        order = OrderService.create_draft_order(user=self.user)

        # Add first item
        OrderService.add_item(order, self.variant1.id, quantity=2)

        # Add second item
        OrderService.add_item(order, self.variant2.id, quantity=3)

        order.refresh_from_db()
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.subtotal, Decimal('2800.00'))  # (500*2) + (600*3)
        self.assertEqual(order.total, Decimal('2800.00'))

    def test_add_same_item_increases_quantity(self):
        """Test adding same item twice increases quantity"""
        order = OrderService.create_draft_order(user=self.user)

        # Add item
        OrderService.add_item(order, self.variant1.id, quantity=2)

        # Add same item again
        OrderService.add_item(order, self.variant1.id, quantity=3)

        order.refresh_from_db()
        self.assertEqual(order.items.count(), 1)  # Still one item

        item = order.items.first()
        self.assertEqual(item.quantity, 5)  # 2 + 3
        self.assertEqual(item.line_total, Decimal('2500.00'))  # 500 * 5

    def test_update_item_quantity(self):
        """Test updating item quantity"""
        order = OrderService.create_draft_order(user=self.user)
        item = OrderService.add_item(order, self.variant1.id, quantity=2)

        # Update quantity
        updated_item = OrderService.update_item_quantity(
            order, item.id, quantity=5
        )

        self.assertEqual(updated_item.quantity, 5)
        self.assertEqual(updated_item.line_total, Decimal('2500.00'))

        order.refresh_from_db()
        self.assertEqual(order.total, Decimal('2500.00'))

    def test_remove_item(self):
        """Test removing item from order"""
        order = OrderService.create_draft_order(user=self.user)
        item = OrderService.add_item(order, self.variant1.id, quantity=2)

        # Remove item
        OrderService.remove_item(order, item.id)

        order.refresh_from_db()
        self.assertEqual(order.items.count(), 0)
        self.assertEqual(order.total, Decimal('0.00'))

    def test_update_item_price(self):
        """Test updating item price"""
        order = OrderService.create_draft_order(user=self.user)
        item = OrderService.add_item(order, self.variant1.id, quantity=2)

        # Update price
        updated_item = OrderService.update_item_price(
            order, item.id, Decimal('450.00')
        )

        self.assertEqual(updated_item.unit_price, Decimal('450.00'))
        self.assertEqual(updated_item.line_total, Decimal('900.00'))

    def test_apply_item_discount(self):
        """Test applying discount to item"""
        order = OrderService.create_draft_order(user=self.user)
        item = OrderService.add_item(order, self.variant1.id, quantity=2)

        # Apply discount
        updated_item = OrderService.apply_item_discount(
            order, item.id, Decimal('100.00')
        )

        self.assertEqual(updated_item.discount_amount, Decimal('100.00'))
        self.assertEqual(updated_item.line_total, Decimal('900.00'))  # 1000 - 100

    def test_apply_order_discount(self):
        """Test applying discount to entire order"""
        order = OrderService.create_draft_order(user=self.user)
        OrderService.add_item(order, self.variant1.id, quantity=2)  # 1000
        OrderService.add_item(order, self.variant2.id, quantity=1)  # 600

        # Apply order-level discount
        OrderService.apply_order_discount(order, Decimal('200.00'))

        order.refresh_from_db()
        self.assertEqual(order.discount_amount, Decimal('200.00'))
        self.assertEqual(order.subtotal, Decimal('1600.00'))
        self.assertEqual(order.total, Decimal('1400.00'))  # 1600 - 200

    def test_clear_order(self):
        """Test clearing all items from order"""
        order = OrderService.create_draft_order(user=self.user)
        OrderService.add_item(order, self.variant1.id, quantity=2)
        OrderService.add_item(order, self.variant2.id, quantity=3)

        # Clear order
        OrderService.clear_order(order)

        order.refresh_from_db()
        self.assertEqual(order.items.count(), 0)
        self.assertEqual(order.total, Decimal('0.00'))

    def test_confirm_order(self):
        """Test confirming order"""
        order = OrderService.create_draft_order(user=self.user)
        OrderService.add_item(order, self.variant1.id, quantity=2)

        initial_stock = self.variant1.stock_quantity

        # Confirm order
        OrderService.confirm_order(order, reduce_stock=True)

        order.refresh_from_db()
        self.assertEqual(order.status, 'CONFIRMED')
        self.assertIsNotNone(order.confirmed_at)

        # Check stock reduced
        self.variant1.refresh_from_db()
        self.assertEqual(self.variant1.stock_quantity, initial_stock - 2)

    def test_cannot_add_item_to_confirmed_order(self):
        """Test that items cannot be added to confirmed orders"""
        order = OrderService.create_draft_order(user=self.user)
        OrderService.add_item(order, self.variant1.id, quantity=1)
        OrderService.confirm_order(order)

        with self.assertRaises(ValidationError):
            OrderService.add_item(order, self.variant2.id, quantity=1)

    def test_insufficient_stock_prevents_add(self):
        """Test that insufficient stock prevents adding item"""
        order = OrderService.create_draft_order(user=self.user)

        # Try to add more than available
        with self.assertRaises(ValidationError) as context:
            OrderService.add_item(
                order,
                self.variant1.id,
                quantity=200  # More than stock (100)
            )

        self.assertIn('Insufficient stock', str(context.exception))

    def test_insufficient_stock_prevents_confirm(self):
        """Test that insufficient stock prevents confirmation"""
        order = OrderService.create_draft_order(user=self.user)
        OrderService.add_item(order, self.variant1.id, quantity=10)

        # Reduce stock after adding
        self.variant1.stock_quantity = 5
        self.variant1.save()

        with self.assertRaises(ValidationError):
            OrderService.confirm_order(order)

    def test_add_payment(self):
        """Test adding payment to order"""
        order = OrderService.create_draft_order(user=self.user)
        OrderService.add_item(order, self.variant1.id, quantity=2)  # Total: 1000
        OrderService.confirm_order(order)

        # Add payment
        payment = OrderService.add_payment(
            order,
            amount=Decimal('1000.00'),
            payment_method='CASH',
            user=self.user
        )

        self.assertEqual(payment.amount, Decimal('1000.00'))

        order.refresh_from_db()
        self.assertEqual(order.amount_paid, Decimal('1000.00'))
        self.assertEqual(order.payment_status, 'PAID')
        self.assertEqual(order.balance_due, Decimal('0.00'))

    def test_partial_payment(self):
        """Test partial payment"""
        order = OrderService.create_draft_order(user=self.user)
        OrderService.add_item(order, self.variant1.id, quantity=2)  # Total: 1000
        OrderService.confirm_order(order)

        # Add partial payment
        OrderService.add_payment(order, Decimal('500.00'))

        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'PARTIAL')
        self.assertEqual(order.balance_due, Decimal('500.00'))

    def test_cancel_order_restocks(self):
        """Test cancelling order restocks items"""
        order = OrderService.create_draft_order(user=self.user)
        OrderService.add_item(order, self.variant1.id, quantity=10)
        OrderService.confirm_order(order)

        initial_stock = self.variant1.stock_quantity

        # Cancel order
        OrderService.cancel_order(order, restock=True)

        order.refresh_from_db()
        self.assertEqual(order.status, 'CANCELLED')

        # Check stock restored
        self.variant1.refresh_from_db()
        self.assertEqual(self.variant1.stock_quantity, initial_stock + 10)

    def test_get_order_summary(self):
        """Test getting order summary"""
        order = OrderService.create_draft_order(
            user=self.user,
            customer_name='John Doe'
        )
        OrderService.add_item(order, self.variant1.id, quantity=2)
        OrderService.add_item(order, self.variant2.id, quantity=1)

        summary = OrderService.get_order_summary(order)

        self.assertEqual(summary['customer']['name'], 'John Doe')
        self.assertEqual(len(summary['items']), 2)
        self.assertEqual(summary['totals']['subtotal'], 1600.0)
        self.assertEqual(summary['item_count'], 3)

    def test_discount_cannot_exceed_subtotal(self):
        """Test that discount cannot exceed subtotal"""
        order = OrderService.create_draft_order(user=self.user)
        OrderService.add_item(order, self.variant1.id, quantity=1)  # 500

        with self.assertRaises(ValidationError):
            OrderService.apply_order_discount(order, Decimal('600.00'))

    def test_cannot_confirm_empty_order(self):
        """Test that empty orders cannot be confirmed"""
        order = OrderService.create_draft_order(user=self.user)

        with self.assertRaises(ValidationError):
            OrderService.confirm_order(order)

# Run tests:
# python manage.py test apps.orders.tests.test_order_services