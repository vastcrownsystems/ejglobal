# apps/orders/models.py
"""
Order management models
"""
from datetime import timedelta

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone

User = get_user_model()


class Order(models.Model):
    """
    Customer order
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('HELD', 'Held'),
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('UNPAID', 'Unpaid'),
        ('PARTIAL', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('REFUNDED', 'Refunded'),
    ]

    # Order identification
    order_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text='Unique order number'
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        db_index=True
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='UNPAID'
    )

    # Customer Association (OPTIONAL)
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,  # ✅ Can be blank for walk-in customers
        related_name='orders',
        help_text="Link to customer record (optional)"
    )

    # Customer info
    customer_name = models.CharField(max_length=200, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)

    # Pricing
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    # Payment
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    # Relationships
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_orders'
    )

    cashier_session = models.ForeignKey(
        'sales.CashierSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Notes
    notes = models.TextField(blank=True)

    # ═══════════════════════════════════════════════════════════
    # ✅ ADD THESE CREDIT SALE FIELDS
    # ═══════════════════════════════════════════════════════════

    SALE_TYPE_CHOICES = [
        ('CASH', 'Cash Sale'),
        ('CREDIT', 'Credit Sale'),
    ]

    sale_type = models.CharField(
        max_length=10,
        choices=SALE_TYPE_CHOICES,
        default='CASH',
        help_text='Sale type determines payment terms',
        db_index=True
    )

    credit_terms_days = models.IntegerField(
        null=True,
        blank=True,
        help_text='Payment due in X days (for credit sales)'
    )

    credit_due_date = models.DateField(
        null=True,
        blank=True,
        help_text='Due date for credit payment',
        db_index=True
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['customer']),
            models.Index(fields=['order_number']),
        ]

    def __str__(self):
        return f"Order {self.order_number} - {self.status}"

    @property
    def customer_display_name(self):
        """
        Get customer name for display

        Priority:
        1. Linked customer name
        2. customer_name field
        3. "Walk-in Customer"
        """
        if self.customer:
            return self.customer.full_name
        elif self.customer_name:
            return self.customer_name
        else:
            return "Walk-in Customer"

    @property
    def customer_contact(self):
        """Get customer contact info"""
        if self.customer:
            return self.customer.phone or self.customer.email
        else:
            return self.customer_phone or self.customer_email or "N/A"

    @property
    def has_customer(self):
        """Check if order has customer info (linked or manual)"""
        return bool(self.customer or self.customer_name)

    @property
    def is_walk_in(self):
        """Check if this is a walk-in (anonymous) sale"""
        return not self.has_customer

    def associate_customer(self, customer):
        """
        Link order to a customer record

        Args:
            customer: Customer instance
        """
        self.customer = customer

        # Update customer stats after saving
        self.save(update_fields=['customer'])

        # Update customer statistics if order is completed
        if self.status == 'COMPLETED':
            customer.update_stats()

    def save(self, *args, **kwargs):
        if not self.order_number:
            # Auto-generate order number
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_order_number():
        """Generate unique order number"""
        from django.utils.timezone import now
        timestamp = now().strftime('%Y%m%d%H%M%S')
        # Add random suffix to handle multiple orders per second
        import random
        suffix = random.randint(100, 999)
        return f'ORD-{timestamp}-{suffix}'

    @property
    def is_draft(self):
        """Check if order is in draft status"""
        return self.status == 'DRAFT'

    @property
    def is_confirmed(self):
        """Check if order is confirmed"""
        return self.status in ['CONFIRMED', 'PROCESSING', 'COMPLETED']

    @property
    def is_paid(self):
        """Check if order is fully paid"""
        return self.payment_status == 'PAID'

    @property
    def balance_due(self):
        """Calculate remaining balance"""
        return self.total - self.amount_paid

    @property
    def item_count(self):
        """Total number of items"""
        return sum(item.quantity for item in self.items.all())

    def update_payment_status(self):
        """
        Update order payment fields based on payments.
        """
        total_paid = sum(p.amount for p in self.order_payments.all())

        self.amount_paid = total_paid

        if total_paid <= 0:
            self.payment_status = "UNPAID"
        elif total_paid < self.total:
            self.payment_status = "PARTIAL"
        else:
            self.payment_status = "PAID"

        self.save(update_fields=["amount_paid", "payment_status"])

    def confirm(self):
        """Confirm the order"""
        if self.status == 'DRAFT':
            self.status = 'CONFIRMED'
            self.confirmed_at = timezone.now()
            self.save()

    # def complete(self):
    #     """Mark order as completed"""
    #     if self.status in ['CONFIRMED', 'PROCESSING']:
    #         self.status = 'COMPLETED'
    #         self.completed_at = timezone.now()
    #         self.save()

    def complete(self):
        """
        Mark order as completed

        Also updates customer stats if customer is linked
        """
        self.status = 'COMPLETED'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])

        # Update customer stats
        if self.customer:
            self.customer.update_stats()

    def cancel(self):
        """Cancel the order"""
        if self.status not in ['COMPLETED', 'CANCELLED']:
            self.status = 'CANCELLED'
            self.save()

    # ═══════════════════════════════════════════════════════════
    # ✅ ADD THESE PROPERTIES
    # ═══════════════════════════════════════════════════════════

    @property
    def is_credit_sale(self):
        """Check if this is a credit sale"""
        return self.sale_type == 'CREDIT'

    @property
    def is_cash_sale(self):
        """Check if this is a cash sale"""
        return self.sale_type == 'CASH'

    @property
    def has_credit_ledger(self):
        """Check if order has associated credit ledger entry"""
        return hasattr(self, 'credit_ledger')

    @property
    def credit_balance_outstanding(self):
        """Get outstanding credit balance for this order"""
        if self.has_credit_ledger:
            return self.credit_ledger.balance_outstanding
        return Decimal('0.00')

    @property
    def is_credit_overdue(self):
        """Check if credit payment is overdue"""
        if self.has_credit_ledger:
            return self.credit_ledger.is_overdue
        return False

    def set_credit_terms(self, days=None):
        """
        Set credit payment terms for this order

        Args:
            days (int): Number of days until payment due
                       If None, uses customer's default terms
        """
        if not days:
            if self.customer and self.customer.credit_terms_days:
                days = self.customer.credit_terms_days
            else:
                days = 30  # Default to Net 30

        self.credit_terms_days = days
        self.credit_due_date = (
                timezone.now().date() + timedelta(days=days)
        )
        self.save(update_fields=['credit_terms_days', 'credit_due_date'])


class OrderItem(models.Model):
    """
    Line item in an order
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )

    variant = models.ForeignKey(
        'catalog.ProductVariant',
        on_delete=models.PROTECT,
        related_name='order_items'
    )

    # Item details (snapshot at time of order)
    product_name = models.CharField(max_length=200)
    variant_name = models.CharField(max_length=200, blank=True)
    sku = models.CharField(max_length=50)

    # Pricing
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    quantity = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )

    line_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    # Discount (optional)
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
        unique_together = ['order', 'variant']

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"

    def save(self, *args, **kwargs):
        # Calculate line total
        self.line_total = (self.unit_price * self.quantity) - self.discount_amount
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        """Subtotal before discount"""
        return self.unit_price * self.quantity


class OrderPayment(models.Model):
    """
    Payment made for an order
    """
    PAYMENT_METHODS = [
        ('CASH', 'Cash'),
        ('CARD', 'Card'),
        ('TRANSFER', 'Bank Transfer'),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        # related_name='payments'
        related_name='order_payments'  # ✅ renamed
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS,
        default='CASH'
    )

    reference_number = models.CharField(
        max_length=100,
        blank=True,
        help_text='Transaction reference'
    )

    notes = models.TextField(blank=True)

    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='payments_created'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.amount} for {self.order.order_number}"