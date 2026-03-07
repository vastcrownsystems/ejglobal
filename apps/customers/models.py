# apps/customers/models.py

from django.db import models

from apps.core.models import TimeStampedModel
from django.core.validators import RegexValidator
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Sum, Q
from decimal import Decimal

User = get_user_model()

class Customer(TimeStampedModel):
    """
       Customer records for sales tracking

       Customers can be:
       - Registered (with full details)
       - Quick add (minimal info)
       - Anonymous (walk-in, no record)
       """

    CUSTOMER_TYPES = [
        ('INDIVIDUAL', 'Individual'),
        ('BUSINESS', 'Business/Corporate'),
    ]

    # Add these fields to Customer model:
    credit_limit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Maximum credit allowed'
    )

    credit_terms_days = models.IntegerField(
        default=30,
        help_text='Default payment terms in days'
    )

    credit_status = models.CharField(
        max_length=20,
        choices=[
            ('APPROVED', 'Approved'),
            ('SUSPENDED', 'Suspended'),
            ('BLOCKED', 'Blocked'),
        ],
        default='APPROVED'
    )

    full_name = models.CharField(max_length=200)
    # Contact Info
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone = models.CharField(
        validators=[phone_regex],
        max_length=17,
        blank=True,
        null=True,
        db_index=True
    )
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True)
    is_walk_in = models.BooleanField(default=False)

    # Basic Info
    customer_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Format: CUST-YYYYMMDD-NNNN",
        blank=True,
        null = True
    )

    # Optional
    address_line = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='Nigeria')

    # Stats (calculated fields)
    total_orders = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    last_purchase_date = models.DateTimeField(null=True, blank=True)

    customer_type = models.CharField(
        max_length=20,
        choices=CUSTOMER_TYPES,
        default='INDIVIDUAL'
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["phone"]), models.Index(fields=["full_name"])]

    def __str__(self):
        return f"{self.customer_number} - {self.full_name}"

    def save(self, *args, **kwargs):
        # Generate customer number if new
        if not self.customer_number:
            self.customer_number = self._generate_customer_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_customer_number():
        """
        Generate unique customer number

        Format: CUST-YYYYMMDD-NNNN
        Example: CUST-20260212-0001
        """
        from django.db import connection

        today = timezone.now().date()
        date_str = today.strftime('%Y%m%d')
        prefix = f"CUST-{date_str}-"

        count = Customer.objects.filter(
            customer_number__startswith=prefix
        ).count()

        sequence = count + 1
        customer_number = f"{prefix}{sequence:04d}"

        return customer_number

    def update_stats(self):
        """
        Update customer statistics from orders

        Call this after completing an order
        """
        from apps.orders.models import Order

        orders = Order.objects.filter(
            customer=self,
            status='COMPLETED'
        )

        self.total_orders = orders.count()
        self.total_spent = orders.aggregate(
            total=models.Sum('total')
        )['total'] or 0

        last_order = orders.order_by('-completed_at').first()
        if last_order:
            self.last_purchase_date = last_order.completed_at

        self.save(update_fields=[
            'total_orders',
            'total_spent',
            'last_purchase_date'
        ])

    def get_orders(self):
        """Get all orders for this customer"""
        return self.orders.all().order_by('-created_at')

    @property
    def outstanding_balance(self):
        """
        Total unpaid balance across all orders

        Returns sum of balance_due for all COMPLETED orders
        with UNPAID or PARTIAL payment status
        """
        from apps.orders.models import Order

        unpaid_orders = Order.objects.filter(
            customer=self,
            status='COMPLETED',
            payment_status__in=['UNPAID', 'PARTIAL']
        )

        total_outstanding = sum(order.balance_due for order in unpaid_orders)
        return total_outstanding

    @property
    def credit_orders_count(self):
        """Number of orders with outstanding balance"""
        from apps.orders.models import Order

        return Order.objects.filter(
            customer=self,
            status='COMPLETED',
            payment_status__in=['UNPAID', 'PARTIAL']
        ).count()

    def get_credit_orders(self):
        """Get all orders with outstanding balance"""
        from apps.orders.models import Order

        return Order.objects.filter(
            customer=self,
            status='COMPLETED',
            payment_status__in=['UNPAID', 'PARTIAL']
        ).select_related('created_by').order_by('-created_at')

    @property
    def has_outstanding_balance(self):
        """Check if customer has any unpaid orders"""
        return self.outstanding_balance > 0

    @property
    def total_credit_outstanding(self):
        """Total outstanding credit balance"""
        try:
            total = self.credit_ledger_entries.filter(
                status__in=['PENDING', 'PARTIAL', 'OVERDUE']
            ).aggregate(
                total=Sum('balance_outstanding')
            )['total']
            return total or Decimal('0.00')
        except:
            return Decimal('0.00')

    @property
    def available_credit(self):
        """Remaining credit available"""
        return self.credit_limit - self.total_credit_outstanding

    def can_extend_credit(self, amount):
        """Check if customer can be extended more credit"""
        if self.credit_status != 'APPROVED':
            return False

        return self.available_credit >= amount

    def get_credit_summary(self):
        """
        Returns summarized credit information for the customer
        """

        ledger = self.credit_ledger_entries.all()

        total_outstanding = ledger.filter(
            status__in=["PENDING", "PARTIAL", "OVERDUE"]
        ).aggregate(
            total=Sum("balance_outstanding")
        )["total"] or Decimal("0.00")

        overdue_balance = ledger.filter(
            status="OVERDUE"
        ).aggregate(
            total=Sum("balance_outstanding")
        )["total"] or Decimal("0.00")

        credit_orders_count = ledger.filter(
            status__in=["PENDING", "PARTIAL", "OVERDUE"]
        ).count()

        available_credit = (self.credit_limit or 0) - total_outstanding

        return {
            "credit_limit": self.credit_limit or Decimal("0.00"),
            "total_outstanding": total_outstanding,
            "available_credit": available_credit,
            "overdue_balance": overdue_balance,
            "credit_status": self.credit_status,
            "credit_orders_count": credit_orders_count,
        }



class CustomerNote(models.Model):
    """
    Notes/comments about customers

    For tracking interactions, preferences, issues
    """
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='customer_notes'
    )

    note = models.TextField()

    # Categorization
    NOTE_TYPES = [
        ('GENERAL', 'General'),
        ('PREFERENCE', 'Preference'),
        ('COMPLAINT', 'Complaint'),
        ('FEEDBACK', 'Feedback'),
        ('CREDIT', 'Credit Note'),
    ]

    note_type = models.CharField(
        max_length=20,
        choices=NOTE_TYPES,
        default='GENERAL'
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    class Meta:
        db_table = 'customer_notes'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer.full_name} - {self.note_type} - {self.created_at.date()}"
