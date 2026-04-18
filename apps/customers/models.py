# apps/customers/models.py

from django.db import models

from apps.core.models import TimeStampedModel
from django.core.validators import RegexValidator
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Sum, Q
from decimal import Decimal

User = get_user_model()


class SalesPerson(TimeStampedModel):
    """
    Sales representatives who can be linked to customers.
    Separate from system users — represents field/sales staff.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_person_profile',
        help_text='Link to system user account (optional)'
    )
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=17, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    employee_id = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text='Employee / staff ID'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['full_name']
        verbose_name = 'Sales Person'
        verbose_name_plural = 'Sales People'

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        if not self.employee_id:
            self.employee_id = self._generate_employee_id()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_employee_id():
        from django.utils import timezone
        timestamp = timezone.now().strftime('%Y%m%d')
        count = SalesPerson.objects.count() + 1
        return f'SP-{timestamp}-{count:04d}'

    @property
    def customer_count(self):
        return self.customers.count()

    @property
    def active_customer_count(self):
        return self.customers.filter(is_active=True).count()


class Customer(TimeStampedModel):
    """
    Customer records for sales tracking.

    Customers can be:
    - Individual (retail consumer)
    - Retailer (resells to end consumers)
    - Distributor (wholesale, bulk buyer)
    - Quick add (minimal info)
    - Anonymous (walk-in, no record)
    """

    CUSTOMER_TYPES = [
        ('RETAILER', 'Retailer'),
        ('DISTRIBUTOR', 'Distributor'),
        ('STAFF', 'Staff'),
    ]

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
    email = models.EmailField(blank=True, null=True, default='')
    address = models.TextField(blank=True)
    is_walk_in = models.BooleanField(default=False)

    customer_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text='Format: CUST-YYYYMMDD-NNNN',
        blank=True,
        null=True
    )

    address_line = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='Nigeria')

    # Stats (calculated fields)
    total_orders = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_purchase_date = models.DateTimeField(null=True, blank=True)

    customer_type = models.CharField(
        max_length=20,
        choices=CUSTOMER_TYPES,
        default='RETAILER',
        db_index=True
    )

    # Sales person assigned to this customer (optional)
    sales_person = models.ForeignKey(
        SalesPerson,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customers',
        help_text='Sales representative assigned to this customer'
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['full_name']),
            models.Index(fields=['customer_type']),
            models.Index(fields=['sales_person']),
        ]

    def __str__(self):
        return f'{self.customer_number} - {self.full_name}'

    def save(self, *args, **kwargs):
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
        today = timezone.now().date()
        date_str = today.strftime('%Y%m%d')
        prefix = f'CUST-{date_str}-'
        count = Customer.objects.filter(
            customer_number__startswith=prefix
        ).count()
        sequence = count + 1
        return f'{prefix}{sequence:04d}'

    def update_stats(self):
        from apps.orders.models import Order
        orders = Order.objects.filter(customer=self, status='COMPLETED')
        self.total_orders = orders.count()
        self.total_spent = orders.aggregate(total=models.Sum('total'))['total'] or 0
        last_order = orders.order_by('-completed_at').first()
        if last_order:
            self.last_purchase_date = last_order.completed_at
        self.save(update_fields=['total_orders', 'total_spent', 'last_purchase_date'])

    def get_orders(self):
        return self.orders.all().order_by('-created_at')

    @property
    def is_distributor(self):
        return self.customer_type == 'DISTRIBUTOR'

    @property
    def is_retailer(self):
        return self.customer_type == 'RETAILER'


    @property
    def is_staff_customer(self):
        return self.customer_type == 'STAFF'

    @property
    def outstanding_balance(self):
        from apps.orders.models import Order
        unpaid_orders = Order.objects.filter(
            customer=self,
            status='COMPLETED',
            payment_status__in=['UNPAID', 'PARTIAL']
        )
        return sum(order.balance_due for order in unpaid_orders)

    @property
    def credit_orders_count(self):
        from apps.orders.models import Order
        return Order.objects.filter(
            customer=self,
            status='COMPLETED',
            payment_status__in=['UNPAID', 'PARTIAL']
        ).count()

    def get_credit_orders(self):
        from apps.orders.models import Order
        return Order.objects.filter(
            customer=self,
            status='COMPLETED',
            payment_status__in=['UNPAID', 'PARTIAL']
        ).select_related('created_by').order_by('-created_at')

    @property
    def has_outstanding_balance(self):
        return self.outstanding_balance > 0

    @property
    def total_credit_outstanding(self):
        try:
            total = self.credit_ledger_entries.filter(
                status__in=['PENDING', 'PARTIAL', 'OVERDUE']
            ).aggregate(total=Sum('balance_outstanding'))['total']
            return total or Decimal('0.00')
        except:
            return Decimal('0.00')

    @property
    def available_credit(self):
        return self.credit_limit - self.total_credit_outstanding

    def can_extend_credit(self, amount):
        if self.credit_status != 'APPROVED':
            return False
        return self.available_credit >= amount

    def get_credit_summary(self):
        ledger = self.credit_ledger_entries.all()
        total_outstanding = ledger.filter(
            status__in=['PENDING', 'PARTIAL', 'OVERDUE']
        ).aggregate(total=Sum('balance_outstanding'))['total'] or Decimal('0.00')

        overdue_balance = ledger.filter(
            status='OVERDUE'
        ).aggregate(total=Sum('balance_outstanding'))['total'] or Decimal('0.00')

        credit_orders_count = ledger.filter(
            status__in=['PENDING', 'PARTIAL', 'OVERDUE']
        ).count()

        available_credit = (self.credit_limit or 0) - total_outstanding

        return {
            'credit_limit': self.credit_limit or Decimal('0.00'),
            'total_outstanding': total_outstanding,
            'available_credit': available_credit,
            'overdue_balance': overdue_balance,
            'credit_status': self.credit_status,
            'credit_orders_count': credit_orders_count,
        }


class CustomerNote(models.Model):
    """
    Notes/comments about customers.
    For tracking interactions, preferences, issues.
    """
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='customer_notes'
    )

    note = models.TextField()

    NOTE_TYPES = [
        ('GENERAL', 'General'),
        ('PREFERENCE', 'Preference'),
        ('COMPLAINT', 'Complaint'),
        ('FEEDBACK', 'Feedback'),
        ('CREDIT', 'Credit Note'),
    ]

    note_type = models.CharField(max_length=20, choices=NOTE_TYPES, default='GENERAL')

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        db_table = 'customer_notes'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.customer.full_name} - {self.note_type} - {self.created_at.date()}'