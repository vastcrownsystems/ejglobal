# apps/customers/models.py
from django.db import models

from apps.core.models import TimeStampedModel
from django.core.validators import RegexValidator
from django.utils import timezone
from django.contrib.auth import get_user_model

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
        default=""
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
