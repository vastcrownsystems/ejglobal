# apps/orders/services.py - COMPLETE WORKING VERSION

from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import Order, OrderItem, OrderPayment
from apps.catalog.models import ProductVariant
import logging
from django.db.models import Sum
from django.db.models.functions import Coalesce

logger = logging.getLogger(__name__)



class OrderService:
    """
    Service for managing orders
    All methods are atomic (database transaction)
    """

    @staticmethod
    @transaction.atomic
    def create_draft_order(user, customer_name='', customer_email='',
                           customer_phone='', notes='', cashier_session=None):
        """
        Create a new draft order
        """
        order = Order.objects.create(
            status='DRAFT',
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            notes=notes,
            created_by=user,
            cashier_session=cashier_session,
            subtotal=Decimal('0.00'),
            total=Decimal('0.00')
        )

        print(f"[OrderService] Created order: {order.order_number}")
        return order

    @staticmethod
    @transaction.atomic
    def add_item(order, variant_id, quantity=1, unit_price=None, discount_amount=None):
        """
        Add item to order or update quantity if already exists

        THIS IS THE CRITICAL METHOD - Make sure it works!
        """
        print(f"\n[add_item] START")
        print(f"  - Order: {order.order_number} (ID: {order.id})")
        print(f"  - Variant ID: {variant_id}")
        print(f"  - Quantity: {quantity}")

        # Validate order status
        if order.status != 'DRAFT':
            raise ValidationError(
                f"Cannot add items to {order.get_status_display()} order"
            )

        # Get variant
        try:
            variant = ProductVariant.objects.select_related('product').get(
                pk=variant_id,
                is_active=True,
                product__is_active=True
            )
            print(f"  - Variant found: {variant.product.name}")
        except ProductVariant.DoesNotExist:
            raise ValidationError("Product variant not found or inactive")

        # Check stock if tracking inventory
        if variant.product.track_inventory:

            # Quantity already in this cart
            existing_qty = (
                    OrderItem.objects
                    .filter(order=order, variant=variant)
                    .aggregate(total=Sum("quantity"))
                    .get("total") or 0
            )

            print(f"  - Stock available: {variant.stock_quantity}")
            print(f"  - Already in cart: {existing_qty}")

            new_total = existing_qty + quantity

            if new_total > variant.stock_quantity:
                available = max(variant.stock_quantity - existing_qty, 0)

                raise ValidationError(
                    f"Only {available} unit(s) of {variant.product.name} "
                    f"({variant.name}) available."
                )

        # Use variant price if not provided
        if unit_price is None:
            unit_price = variant.price

        # Default discount
        if discount_amount is None:
            discount_amount = Decimal('0.00')

        print(f"  - Unit price: ₦{unit_price}")
        print(f"  - Discount: ₦{discount_amount}")

        # Check if item already exists in order
        try:
            item = OrderItem.objects.get(order=order, variant=variant)
            print(f"  - Item exists, updating quantity from {item.quantity} to {item.quantity + quantity}")
            # Update existing item
            item.quantity += quantity
            item.unit_price = unit_price
            item.discount_amount = discount_amount
            item.save()
            print(f"  - Item updated: ID={item.id}")
        except OrderItem.DoesNotExist:
            print(f"  - Creating new item")
            # Create new item
            item = OrderItem.objects.create(
                order=order,
                variant=variant,
                product_name=variant.product.name,
                variant_name=str(variant),
                sku=variant.sku,
                unit_price=unit_price,
                quantity=quantity,
                discount_amount=discount_amount
            )
            print(f"  - Item created: ID={item.id}")

        # Recalculate order totals
        print(f"  - Recalculating totals...")
        OrderService._recalculate_totals(order)

        # Verify item was saved
        item.refresh_from_db()
        print(f"  - Final item: {item.product_name} x{item.quantity} = ₦{item.line_total}")
        print(f"[add_item] END\n")

        return item

    @staticmethod
    @transaction.atomic
    def update_item_quantity(order, item_id, quantity):
        """Update quantity of an order item"""
        if order.status != 'DRAFT':
            raise ValidationError("Cannot modify confirmed orders")

        if quantity < 1:
            raise ValidationError("Quantity must be at least 1")

        try:
            item = OrderItem.objects.select_related('variant').get(
                pk=item_id,
                order=order
            )
        except OrderItem.DoesNotExist:
            raise ValidationError("Order item not found")

        # Check stock
        if item.variant.product.track_inventory:
            if item.variant.stock_quantity < quantity:
                raise ValidationError(
                    f"Insufficient stock. Available: {item.variant.stock_quantity}, "
                    f"Requested: {quantity}"
                )

        # Update quantity
        item.quantity = quantity
        item.save()

        # Recalculate totals
        OrderService._recalculate_totals(order)

        return item

    @staticmethod
    @transaction.atomic
    def remove_item(order, item_id):
        """Remove item from order"""
        if order.status != 'DRAFT':
            raise ValidationError("Cannot modify confirmed orders")

        try:
            item = OrderItem.objects.get(pk=item_id, order=order)
            item.delete()
        except OrderItem.DoesNotExist:
            raise ValidationError("Order item not found")

        # Recalculate totals
        OrderService._recalculate_totals(order)

    @staticmethod
    @transaction.atomic
    def clear_order(order):
        """Remove all items from order"""
        if order.status != 'DRAFT':
            raise ValidationError("Cannot modify confirmed orders")

        # Delete all items
        order.items.all().delete()

        # Reset totals
        order.subtotal = Decimal('0.00')
        order.discount_amount = Decimal('0.00')
        order.tax_amount = Decimal('0.00')
        order.total = Decimal('0.00')
        order.save()

        return order

    @staticmethod
    @transaction.atomic
    def apply_order_discount(order, discount_amount):
        """Apply discount to entire order"""
        if order.status != 'DRAFT':
            raise ValidationError("Cannot modify confirmed orders")

        if discount_amount < 0:
            raise ValidationError("Discount cannot be negative")

        if discount_amount > order.subtotal:
            raise ValidationError(
                f"Discount cannot exceed order subtotal (₦{order.subtotal})"
            )

        order.discount_amount = discount_amount
        order.save()

        OrderService._recalculate_totals(order)
        return order

    # @staticmethod
    # def _recalculate_totals(order):
    #     """
    #     Recalculate order totals
    #
    #     THIS IS CRITICAL - Make sure it saves!
    #     """
    #     print(f"  [_recalculate_totals] START for order {order.order_number}")
    #
    #     # Calculate subtotal from items
    #     items = order.items.all()
    #     subtotal = sum(item.line_total for item in items)
    #
    #     print(f"  [_recalculate_totals] Items count: {items.count()}")
    #     print(f"  [_recalculate_totals] Subtotal: ₦{subtotal}")
    #
    #     # Update order
    #     order.subtotal = subtotal
    #     order.tax_amount = Decimal('0.00')  # No tax for now
    #     order.total = subtotal + order.tax_amount - order.discount_amount
    #
    #     # Ensure total doesn't go negative
    #     if order.total < 0:
    #         order.total = Decimal('0.00')
    #
    #     print(f"  [_recalculate_totals] Total: ₦{order.total}")
    #
    #     # ✅ CRITICAL: Actually save the order!
    #     order.save(update_fields=['subtotal', 'tax_amount', 'total', 'updated_at'])
    #
    #     print(f"  [_recalculate_totals] Order saved!")
    #     print(f"  [_recalculate_totals] END\n")

    @staticmethod
    def _recalculate_totals(order):
        """
        Recalculate order totals correctly
        """

        items = order.items.all()

        # Subtotal BEFORE any discount
        subtotal = sum(item.unit_price * item.quantity for item in items)

        # Total item-level discounts
        total_item_discounts = sum(item.discount_amount for item in items)

        # Cart-level discount (if you later support it)
        cart_discount = order.discount_amount or Decimal('0.00')

        total_discount = total_item_discounts + cart_discount

        # Update order
        order.subtotal = subtotal
        order.discount_amount = total_item_discounts
        order.tax_amount = Decimal('0.00')

        order.total = subtotal - total_item_discounts + order.tax_amount

        if order.total < 0:
            order.total = Decimal('0.00')

        order.save(update_fields=[
            'subtotal',
            'discount_amount',
            'tax_amount',
            'total',
            'updated_at'
        ])

    """Service for managing orders with payment and inventory integration"""

    # ... (previous methods: create_draft_order, add_item, etc.)

    @staticmethod
    @transaction.atomic
    def add_payment(order, amount, payment_method='CASH',
                    reference_number='', notes='', user=None):
        """
        Add payment to order

        Args:
            order: Order instance
            amount: Payment amount (Decimal)
            payment_method: Payment method code (CASH, CARD, etc.)
            reference_number: Transaction reference (optional)
            notes: Payment notes (optional)
            user: User making payment (optional)

        Returns:
            OrderPayment instance

        Raises:
            ValidationError: If payment invalid
        """
        logger.info(f"Adding payment to order {order.order_number}")

        # Validate amount
        if amount <= 0:
            raise ValidationError("Payment amount must be greater than zero")

        # Check if overpaying
        if amount > order.balance_due:
            raise ValidationError(
                f"Payment amount (₦{amount}) exceeds balance due (₦{order.balance_due})"
            )

        # Create payment
        payment = OrderPayment.objects.create(
            order=order,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference_number,
            notes=notes,
            created_by=user
        )

        # Update order payment status
        order.update_payment_status()

        logger.info(
            f"Payment added: ₦{amount} via {payment_method}. "
            f"Balance: ₦{order.balance_due}"
        )

        return payment

    @staticmethod
    @transaction.atomic
    def confirm_order(order, reduce_stock=True):
        """
        Confirm order and optionally reduce stock

        This transitions order from DRAFT to CONFIRMED
        and creates inventory movements if reduce_stock=True

        Args:
            order: Order instance
            reduce_stock: Whether to reduce inventory (default True)

        Raises:
            ValidationError: If order cannot be confirmed
        """
        logger.info(f"Confirming order {order.order_number}")

        # Validate order status
        if order.status != 'DRAFT':
            raise ValidationError(
                f"Cannot confirm order with status: {order.get_status_display()}"
            )

        # Validate order has items
        if order.items.count() == 0:
            raise ValidationError("Cannot confirm empty order")

        # Check stock availability if reducing
        if reduce_stock:
            OrderService._check_stock_availability(order)

        # Confirm order
        order.confirm()

        # Reduce stock if requested
        if reduce_stock:
            from apps.inventory.services import InventoryService
            InventoryService.process_order_sale(order)

        logger.info(f"Order {order.order_number} confirmed")

        return order

    @staticmethod
    def _check_stock_availability(order):
        """
        Check if all items have sufficient stock

        Raises:
            ValidationError: If any item has insufficient stock
        """
        insufficient_items = []

        for item in order.items.all():
            variant = item.variant

            # Skip if not tracking inventory
            if not variant.product.track_inventory:
                continue

            # Check stock
            if variant.stock_quantity < item.quantity:
                insufficient_items.append(
                    f"{item.product_name}: Need {item.quantity}, "
                    f"Available {variant.stock_quantity}"
                )

        if insufficient_items:
            raise ValidationError(
                "Insufficient stock:\n" + "\n".join(insufficient_items)
            )

    @staticmethod
    @transaction.atomic
    def complete_order(order):
        """
        Complete the order transaction

        This is the main method that:
        1. Validates payment is complete
        2. Confirms order (if not already)
        3. Reduces inventory
        4. Marks order as COMPLETED
        5. Generates receipt

        Args:
            order: Order instance

        Returns:
            Receipt instance

        Raises:
            ValidationError: If order cannot be completed
        """
        logger.info(f"Completing order {order.order_number}")

        # Validate order has items
        if order.items.count() == 0:
            raise ValidationError("Cannot complete empty order")

        # Validate payment
        if not order.is_paid:
            raise ValidationError(
                f"Order not fully paid. Balance due: ₦{order.balance_due}"
            )

        # Confirm if still draft
        if order.status == 'DRAFT':
            OrderService.confirm_order(order, reduce_stock=True)

        # Mark as completed
        order.complete()

        # Generate receipt
        from apps.receipts.services import ReceiptService
        receipt = ReceiptService.generate_receipt(order)

        logger.info(
            f"Order {order.order_number} completed. "
            f"Receipt: {receipt.receipt_number}"
        )

        return receipt

    @staticmethod
    @transaction.atomic
    def cancel_order(order, reason='', user=None):
        """
        Cancel order and restore stock

        Args:
            order: Order instance
            reason: Cancellation reason
            user: User cancelling order

        Raises:
            ValidationError: If order cannot be cancelled
        """
        logger.info(f"Cancelling order {order.order_number}")

        # Validate can cancel
        if order.status in ['COMPLETED', 'CANCELLED']:
            raise ValidationError(
                f"Cannot cancel {order.get_status_display()} order"
            )

        # If order was confirmed, restore stock
        if order.status in ['CONFIRMED', 'PROCESSING']:
            from apps.inventory.services import InventoryService
            InventoryService.restore_order_stock(order)

        # Cancel order
        order.cancel()

        # Add cancellation note
        if reason:
            order.notes = f"CANCELLED: {reason}\n{order.notes or ''}"
            order.save(update_fields=['notes'])

        logger.info(f"Order {order.order_number} cancelled")

        return order







