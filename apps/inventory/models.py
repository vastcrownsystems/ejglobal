# apps/inventory/models.py
"""
Inventory management - Stock movements and adjustments
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator

User = get_user_model()


class PendingStockAdjustment(models.Model):
    """
    Pending stock adjustments that require manager approval
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    variant = models.ForeignKey(
        'catalog.ProductVariant',
        on_delete=models.CASCADE,
        related_name='pending_adjustments'
    )

    adjustment_type = models.CharField(
        max_length=10,
        choices=[('increase', 'Increase'), ('decrease', 'Decrease')]
    )

    quantity = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text='Amount to adjust'
    )

    quantity_change = models.IntegerField(
        help_text='Calculated change (positive or negative)'
    )

    reason = models.CharField(
        max_length=20,
        choices=[
            ('damaged', 'Damaged'),
            ('expired', 'Expired'),
            ('lost', 'Lost/Theft'),
            ('recount', 'Stock Recount'),
            ('correction', 'Correction'),
            ('other', 'Other'),
        ]
    )

    notes = models.TextField(blank=True)

    # Tracking
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    requested_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='stock_adjustment_requests'
    )

    requested_at = models.DateTimeField(auto_now_add=True)

    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_stock_adjustments'
    )

    reviewed_at = models.DateTimeField(null=True, blank=True)

    review_notes = models.TextField(blank=True)

    # Stock at time of request
    stock_at_request = models.IntegerField()

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['status', '-requested_at']),
            models.Index(fields=['variant', 'status']),
        ]

    def __str__(self):
        sign = '+' if self.quantity_change >= 0 else ''
        return f"{self.variant.sku}: {sign}{self.quantity_change} ({self.status})"

    @property
    def is_pending(self):
        return self.status == 'PENDING'

    @property
    def can_be_approved(self):
        """Check if adjustment can still be approved"""
        if self.status != 'PENDING':
            return False

        # Check if stock hasn't changed significantly
        current_stock = self.variant.stock_quantity
        if abs(current_stock - self.stock_at_request) > 10:
            return False

        return True


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