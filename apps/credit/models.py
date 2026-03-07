# apps/credit/models.py
# ✅ COMPLETE FIXED VERSION - Updates order payment status

"""
Enterprise Credit Ledger (Accounts Receivable) Models
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db.models import Sum, Q
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class CreditLedger(models.Model):
    """
    Main ledger tracking all credit transactions
    Central record for accounts receivable
    """
    TRANSACTION_TYPES = [
        ('SALE', 'Credit Sale'),
        ('PAYMENT', 'Payment Received'),
        ('ADJUSTMENT', 'Balance Adjustment'),
        ('WRITEOFF', 'Bad Debt Write-off'),
        ('REFUND', 'Refund Issued'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PARTIAL', 'Partially Paid'),
        ('PAID', 'Paid in Full'),
        ('OVERDUE', 'Overdue'),
        ('WRITTEN_OFF', 'Written Off'),
    ]

    # Identification
    ledger_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text='Unique ledger identifier'
    )

    # Links
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.PROTECT,
        related_name='credit_ledger_entries',
        help_text='Customer who owes money'
    )

    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='credit_ledger',
        help_text='Related order for credit sale'
    )

    # Transaction Details
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES,
        default='SALE'
    )

    transaction_date = models.DateTimeField(
        default=timezone.now,
        db_index=True
    )

    # Amounts
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Total credit amount',
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Total paid so far',
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    balance_outstanding = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Remaining balance',
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    # Status & Terms
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )

    due_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Payment due date'
    )

    terms_days = models.IntegerField(
        default=30,
        help_text='Payment terms in days'
    )

    # Tracking
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='credit_ledgers_created'
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['customer', '-transaction_date']),
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['-transaction_date']),
            models.Index(fields=['ledger_id']),
        ]
        verbose_name = 'Credit Ledger Entry'
        verbose_name_plural = 'Credit Ledger Entries'

    def __str__(self):
        return f"{self.ledger_id} - {self.customer} - ₦{self.balance_outstanding}"

    def save(self, *args, **kwargs):
        # Auto-generate ledger ID
        if not self.ledger_id:
            self.ledger_id = self.generate_ledger_id()

        # Calculate balance
        if self.total_amount is not None and self.amount_paid is not None:
            self.balance_outstanding = self.total_amount - self.amount_paid

        super().save(*args, **kwargs)

    @staticmethod
    def generate_ledger_id():
        """Generate unique ledger ID"""
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        import random
        suffix = random.randint(100, 999)
        return f'CL-{timestamp}-{suffix}'

    @property
    def is_overdue(self):
        """Check if payment is overdue"""
        if self.due_date and self.balance_outstanding > 0:
            return timezone.now().date() > self.due_date
        return False

    @property
    def days_overdue(self):
        """Calculate days overdue"""
        if self.is_overdue:
            return (timezone.now().date() - self.due_date).days
        return 0

    @property
    def days_until_due(self):
        """Calculate days until due"""
        if self.due_date and self.balance_outstanding > 0:
            delta = self.due_date - timezone.now().date()
            return delta.days
        return None

    @property
    def payment_percentage(self):
        """Calculate percentage paid"""
        if self.total_amount > 0:
            return (self.amount_paid / self.total_amount) * 100
        return 0

    def update_status(self):
        """Update status based on payment and due date"""
        if self.balance_outstanding <= 0:
            self.status = 'PAID'
        elif self.amount_paid > 0:
            if self.is_overdue:
                self.status = 'OVERDUE'
            else:
                self.status = 'PARTIAL'
        elif self.is_overdue:
            self.status = 'OVERDUE'
        else:
            self.status = 'PENDING'

        self.save(update_fields=['status'])

    def update_from_payments(self):
        """
        Recalculate amounts from payment records
        ✅ FIXED: Also updates order payment status
        """
        total_paid = self.payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        self.amount_paid = total_paid
        self.balance_outstanding = self.total_amount - total_paid
        self.save(update_fields=['amount_paid', 'balance_outstanding'])

        self.update_status()

        # ✅ UPDATE ORDER PAYMENT STATUS
        self.update_order_payment_status()

    def update_order_payment_status(self):
        """
        Update the related order's payment status based on credit balance

        - If balance is 0 → payment_status = 'PAID'
        - If partially paid → payment_status = 'PARTIAL'
        - If unpaid → payment_status = 'UNPAID'
        """
        if not self.order:
            return

        if self.balance_outstanding <= 0:
            # Fully paid
            self.order.payment_status = 'PAID'
        elif self.amount_paid > 0:
            # Partially paid
            self.order.payment_status = 'PARTIAL'
        else:
            # Unpaid
            self.order.payment_status = 'UNPAID'

        self.order.save(update_fields=['payment_status'])


class CreditPayment(models.Model):
    """
    Individual payments made against credit ledger entries
    Tracks when and how customers pay their credit balances
    """
    PAYMENT_METHODS = [
        ('CASH', 'Cash'),
        ('CARD', 'Card'),
        ('TRANSFER', 'Bank Transfer'),
    ]

    # Identification
    payment_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text='Unique payment identifier'
    )

    # Links
    ledger = models.ForeignKey(
        CreditLedger,
        on_delete=models.PROTECT,
        related_name='payments',
        help_text='Credit ledger entry this payment is for'
    )

    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.PROTECT,
        related_name='credit_payments',
        help_text='Customer making payment'
    )

    # Payment Details
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Payment amount'
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS,
        default='CASH'
    )

    payment_date = models.DateTimeField(
        default=timezone.now,
        db_index=True
    )

    reference_number = models.CharField(
        max_length=100,
        blank=True,
        help_text='Transaction reference'
    )

    # Tracking
    received_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='credit_payments_received',
        help_text='Staff who received payment'
    )

    cashier_session = models.ForeignKey(
        'sales.CashierSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='credit_payments'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['ledger', '-payment_date']),
            models.Index(fields=['customer', '-payment_date']),
            models.Index(fields=['-payment_date']),
        ]
        verbose_name = 'Credit Payment'
        verbose_name_plural = 'Credit Payments'

    def __str__(self):
        return f"{self.payment_id} - ₦{self.amount}"

    def save(self, *args, **kwargs):
        # Auto-generate payment ID
        if not self.payment_id:
            self.payment_id = self.generate_payment_id()

        # Ensure customer matches ledger
        if not self.customer:
            self.customer = self.ledger.customer

        super().save(*args, **kwargs)

        # Update ledger after payment (which now also updates order)
        self.update_ledger()

    @staticmethod
    def generate_payment_id():
        """Generate unique payment ID"""
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        import random
        suffix = random.randint(100, 999)
        return f'CPMT-{timestamp}-{suffix}'

    def update_ledger(self):
        """Update related ledger entry"""
        self.ledger.update_from_payments()