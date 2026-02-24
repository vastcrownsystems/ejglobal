# apps/inventory/services.py
"""
Inventory service - Handles all stock adjustments atomically
"""
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import StockMovement
from apps.catalog.models import ProductVariant
from decimal import Decimal
import logging
from django.utils import timezone
from apps.orders.models import Order

logger = logging.getLogger(__name__)

class InventoryService:
    """
    Service for safe stock management
    All stock changes MUST go through this service
    """

    @staticmethod
    @transaction.atomic
    def adjust_stock(
            variant_id,
            quantity_change,
            user,
            reason='',
            notes='',
            movement_type='ADJ',
            reference_type='',
            reference_id=None,
            reference_number='',
            unit_cost=None,
            created_by=None,
    ):
        """
        Adjust stock quantity atomically

        Args:
            variant_id: ProductVariant ID
            quantity_change: int (positive = increase, negative = decrease)
            user: User making the adjustment
            reason: Reason for adjustment
            notes: Additional notes
            movement_type: Type of movement (default: ADJ)
            reference_type: Type of reference type (default: '')
            reference_id: Reference ID (optional)
            reference_number: Reference number (optional)
            unit_cost: Unit cost (optional)
            created_by: User making the adjustment

        Returns:
            StockMovement instance

        Raises:
            ValidationError: If stock would go negative
        """
        # Lock the variant row to prevent race conditions
        variant = ProductVariant.objects.select_for_update().get(pk=variant_id)

        stock_before = variant.stock_quantity
        stock_after = stock_before + quantity_change

        if stock_after < 0:
            raise ValidationError(
                f"Cannot reduce stock below 0. "
                f"Current: {stock_before}, Change: {quantity_change}, Result: {stock_after}"
            )

        # Update variant stock
        variant.stock_quantity = stock_after
        variant.save(update_fields=['stock_quantity'])

        # Create movement record (single source of truth)
        movement = StockMovement.objects.create(
            variant=variant,
            movement_type=movement_type,
            quantity=abs(quantity_change),  # store absolute quantity
            stock_before=stock_before,
            stock_after=stock_after,
            reason=reason if movement_type == 'ADJ' else '',
            notes=notes,

            # keep your existing field
            user=user,

            # support your newer fields used elsewhere
            reference_type=reference_type or '',
            reference_id=reference_id,
            reference_number=reference_number or '',
            unit_cost=unit_cost if unit_cost is not None else Decimal('0.00'),
            created_by=created_by or user,
        )

        return movement

    @staticmethod
    @transaction.atomic
    def record_sale(variant_id, quantity, user, sale_id=None):
        """
        Record stock decrease from a sale
        """
        return InventoryService.adjust_stock(
            variant_id=variant_id,
            quantity_change=-abs(quantity),  # Always negative
            user=user,
            notes=f'Sale #{sale_id}' if sale_id else 'Sale',
            movement_type='SALE'
        )

    @staticmethod
    @transaction.atomic
    def record_restock(variant_id, quantity, user, notes=''):
        """
        Record stock increase from restock/purchase
        """
        return InventoryService.adjust_stock(
            variant_id=variant_id,
            quantity_change=abs(quantity),  # Always positive
            user=user,
            notes=notes or 'Restock',
            movement_type='RESTOCK'
        )

    @staticmethod
    def get_movement_history(variant_id=None, limit=100):
        """
        Get stock movement history
        """
        movements = StockMovement.objects.select_related(
            'variant',
            'variant__product',
            'user'
        )

        if variant_id:
            movements = movements.filter(variant_id=variant_id)

        return movements[:limit]

    """Service for managing inventory and stock movements"""

    @staticmethod
    @transaction.atomic
    def process_order_sale(order):
        """
        Process inventory for order sale

        Creates OUT movements and reduces stock for all items

        Args:
            order: Order instance

        Raises:
            ValidationError: If insufficient stock
        """
        logger.info(f"Processing inventory for order {order.order_number}")

        movements_created = []

        try:
            for item in order.items.select_related('variant', 'variant__product').all():
                variant = item.variant

                # Skip if not tracking inventory
                if not variant.product.track_inventory:
                    logger.info(
                        f"Skipping {item.product_name} - inventory not tracked"
                    )
                    continue

                # Check stock availability
                if variant.stock_quantity < item.quantity:
                    raise ValidationError(
                        f"Insufficient stock for {item.product_name}. "
                        f"Available: {variant.stock_quantity}, "
                        f"Required: {item.quantity}"
                    )

                movement = InventoryService.adjust_stock(
                    variant_id=variant.id,
                    quantity_change=-item.quantity,
                    user=order.created_by,
                    movement_type='OUT',  # or 'SALE' if you prefer consistent naming
                    notes=f"Sale - Order {order.order_number}",
                    reference_type='ORDER',
                    reference_id=order.id,
                    reference_number=order.order_number,
                    unit_cost=item.unit_price,
                    created_by=order.created_by,
                )
                movements_created.append(movement)

                logger.info(
                    f"Stock reduced: {item.product_name} "
                    f"(-{item.quantity}) = {movement.stock_after}"
                )

            logger.info(
                f"Created {len(movements_created)} stock movements for "
                f"order {order.order_number}"
            )

            return movements_created

        except Exception as e:
            logger.exception(f"Error processing inventory: {e}")
            raise

    @staticmethod
    @transaction.atomic
    def restore_order_stock(order):
        """
        Restore stock for cancelled/returned order

        Creates IN movements to restore stock

        Args:
            order: Order instance
        """
        logger.info(f"Restoring stock for order {order.order_number}")

        movements_created = []

        for item in order.items.select_related('variant', 'variant__product').all():
            variant = item.variant

            # Skip if not tracking inventory
            if not variant.product.track_inventory:
                continue

            # Create IN movement (restoration)
            movement = InventoryService.adjust_stock(
                variant_id=variant.id,
                quantity_change=item.quantity,
                user=order.created_by,
                movement_type='IN',
                notes=f"Stock restoration - Order {order.order_number} cancelled",
                reference_type='ORDER_CANCEL',
                reference_id=order.id,
                reference_number=order.order_number,
                unit_cost=item.unit_price,
                created_by=order.created_by,
            )

            movements_created.append(movement)

            logger.info(
                f"Stock restored: {item.product_name} "
                f"(+{item.quantity}) = {movement.stock_after}"
            )

        logger.info(
            f"Restored stock for {len(movements_created)} items "
            f"from order {order.order_number}"
        )

        return movements_created


    @staticmethod
    def check_stock_availability(variant, quantity):
        """
        Check if sufficient stock available

        Args:
            variant: ProductVariant instance
            quantity: Required quantity

        Returns:
            dict with 'available' (bool) and 'current_stock' (int)
        """
        # If not tracking inventory, always available
        if not variant.product.track_inventory:
            return {
                'available': True,
                'current_stock': None,
                'tracking': False
            }

        available = variant.stock_quantity >= quantity

        return {
            'available': available,
            'current_stock': variant.stock_quantity,
            'requested': quantity,
            'tracking': True
        }

    @staticmethod
    def get_low_stock_products(threshold=None):
        """
        Get products with low stock

        Args:
            threshold: Stock threshold (uses variant.low_stock_threshold if None)

        Returns:
            QuerySet of ProductVariants
        """
        from django.db.models import Q

        if threshold is None:
            # Use each variant's own threshold
            low_stock = ProductVariant.objects.filter(
                product__track_inventory=True,
                is_active=True
            ).filter(
                Q(stock_quantity__lte=models.F('low_stock_threshold')) |
                Q(stock_quantity=0)
            )
        else:
            # Use provided threshold
            low_stock = ProductVariant.objects.filter(
                product__track_inventory=True,
                is_active=True,
                stock_quantity__lte=threshold
            )

        return low_stock.select_related('product', 'product__category')

    @staticmethod
    def get_stock_value():
        """
        Calculate total stock value

        Returns:
            dict with stock value details
        """
        from django.db.models import Sum, F, DecimalField
        from django.db.models.functions import Coalesce

        result = ProductVariant.objects.filter(
            product__track_inventory=True,
            is_active=True
        ).aggregate(
            total_units=Coalesce(Sum('stock_quantity'), 0),
            total_value=Coalesce(
                Sum(F('stock_quantity') * F('cost'),
                    output_field=DecimalField()),
                Decimal('0.00')
            )
        )

        return {
            'total_units': result['total_units'],
            'total_value': result['total_value'],
            'currency': '₦'
        }