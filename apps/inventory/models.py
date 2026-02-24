# apps/inventory/models.py
"""
Inventory management - Stock movements and adjustments
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator

User = get_user_model()


class StockMovement(models.Model):
    """
    Audit log for all stock changes
    """
    MOVEMENT_TYPES = [
        ('ADJ', 'Adjustment'),
        ('SALE', 'Sale'),
        ('RESTOCK', 'Restock'),
        ('DAMAGE', 'Damage/Loss'),
        ('RETURN', 'Return'),
    ]

    ADJUSTMENT_REASONS = [
        ('damaged', 'Damaged'),
        ('expired', 'Expired'),
        ('lost', 'Lost/Theft'),
        ('recount', 'Stock Recount'),
        ('correction', 'Correction'),
        ('other', 'Other'),
    ]

    REFERENCE_TYPES = [
        ('PURCHASE', 'Purchase'),
        ('ORDER', 'Sale Order'),
        ('ORDER_CANCEL', 'Order Cancellation'),
        ('ADJUSTMENT', 'Manual Adjustment'),
        ('RETURN', 'Customer Return'),
        ('DAMAGE', 'Damage/Loss'),
        ('TRANSFER', 'Transfer'),
    ]

    reference_type = models.CharField(
        max_length=20,
        choices=REFERENCE_TYPES,
        help_text="Type of transaction"
    )

    variant = models.ForeignKey(
        'catalog.ProductVariant',
        on_delete=models.CASCADE,
        related_name='stock_movements'
    )

    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPES)

    quantity = models.IntegerField(
        help_text='Positive = increase, Negative = decrease'
    )

    stock_before = models.IntegerField()
    stock_after = models.IntegerField(validators=[MinValueValidator(0)])

    reason = models.CharField(
        max_length=20,
        choices=ADJUSTMENT_REASONS,
        blank=True
    )

    notes = models.TextField(blank=True)

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # link to source document
    reference_id = models.IntegerField(null=True, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)

    # financial trace
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # who performed the action
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="stock_movements"
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['variant', '-created_at']),
            models.Index(fields=['movement_type', '-created_at']),
        ]

    def __str__(self):
        sign = '+' if self.quantity >= 0 else ''
        return f"{self.variant.sku}: {sign}{self.quantity}"

    @property
    def quantity_display(self):
        """Display with +/- sign"""
        return f"+{self.quantity}" if self.quantity >= 0 else str(self.quantity)