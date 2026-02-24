from django.db import transaction
from django.core.exceptions import ValidationError
import logging
from .models import Customer, CustomerNote

logger = logging.getLogger(__name__)

class CustomerService:
    """Service for managing customers"""

    @staticmethod
    @transaction.atomic
    def quick_add(full_name, phone="", email="", customer_type="", created_by=None):
        """
        Quick add customer with minimal info

        Used in POS for fast customer creation

        Args:
            full_name: Customer name (required)
            phone: Phone number (optional)
            email: Email (optional)
            customer_type: INDIVIDUAL or BUSINESS
            created_by: User creating customer

        Returns:
            Customer instance
        """
        logger.info(f"Quick adding customer {full_name}")

        # Validate name
        if not full_name or not full_name.strip():
            raise ValidationError("Customer name is required")

        # Create customer
        customer = Customer.objects.create(
            full_name=full_name.strip(),
            phone=phone.strip() if phone else "",
            email=email.strip() if email else "",
            customer_type=customer_type,
            created_by=created_by
        )

        logger.info(f"Customer Created: {customer.customer_number}")

        return customer

    @staticmethod
    @transaction.atomic
    def create_customer(full_name, phone="", email="", customer_type="INDIVIDUAL",
                        address_line='', city="", state="", postal_code="", created_by=None):
        """
        Create customer with full details

        Args:
            full_name: Customer name
            phone: Phone number
            email: Email
            customer_type: INDIVIDUAL or BUSINESS
            address_line: Address line
            city: City
            state: State
            postal_code: Postal code
            created_by: User creating customer

        Returns:
            Customer instance
        """
        logger.info(f"Creating customer: {full_name}")

        # Validate
        if not full_name or not full_name.strip():
            raise ValidationError("Customer name is required")

        # Create customer
        customer = Customer.objects.create(
            full_name=full_name.strip(),
            phone=phone.strip() if phone else '',
            email=email.strip() if email else '',
            customer_type=customer_type,
            address_line=address_line.strip() if address_line else '',
            city=city.strip() if city else '',
            state=state.strip() if state else '',
            postal_code=postal_code.strip() if postal_code else '',
            created_by=created_by
        )

        logger.info(f"Customer created: {customer.customer_number}")

        return customer

    @staticmethod
    def search_customers(query, limit=10):
        """
        Search customers by full_name, phone, email, or number

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            QuerySet of customers
        """
        from django.db.models import Q

        if not query or len(query) < 2:
            return Customer.objects.none()

        customers = Customer.objects.filter(
            Q(full_name__icontains=query) |
            Q(customer_number__icontains=query) |
            Q(phone__icontains=query) |
            Q(email__icontains=query),
            is_active=True
        ).order_by('-total_spent')[:limit]

        return customers

    @staticmethod
    def find_by_phone(phone):
        """
        Find customer by phone number

        Args:
            phone: Phone number

        Returns:
            Customer instance or None
        """
        try:
            return Customer.objects.get(phone=phone, is_active=True)
        except Customer.DoesNotExist:
            return None
        except Customer.MultipleObjectsReturned:
            # Return most recent
            return Customer.objects.filter(
                phone=phone,
                is_active=True
            ).order_by('-created_at').first()

    @staticmethod
    def find_by_email(email):
        """
        Find customer by email

        Args:
            email: Email address

        Returns:
            Customer instance or None
        """
        try:
            return Customer.objects.get(email=email, is_active=True)
        except Customer.DoesNotExist:
            return None
        except Customer.MultipleObjectsReturned:
            return Customer.objects.filter(
                email=email,
                is_active=True
            ).order_by('-created_at').first()

    @staticmethod
    @transaction.atomic
    def add_note(customer, note_text, note_type='GENERAL', created_by=None):
        """
        Add note to customer

        Args:
            customer: Customer instance
            note_text: Note text
            note_type: Note type (GENERAL, PREFERENCE, etc.)
            created_by: User creating note

        Returns:
            CustomerNote instance
        """
        note = CustomerNote.objects.create(
            customer=customer,
            note=note_text,
            note_type=note_type,
            created_by=created_by
        )

        logger.info(f"Note added to customer {customer.customer_number}")

        return note

    @staticmethod
    def get_customer_stats(customer):
        """
        Get detailed customer statistics

        Args:
            customer: Customer instance

        Returns:
            dict with statistics
        """
        from apps.orders.models import Order
        from django.db.models import Sum, Avg, Count
        from datetime import timedelta
        from django.utils import timezone

        # Get all completed orders
        orders = Order.objects.filter(
            customer=customer,
            status='COMPLETED'
        )

        # Calculate stats
        stats = orders.aggregate(
            total_orders=Count('id'),
            total_spent=Sum('total'),
            average_order=Avg('total'),
        )

        # Recent orders (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_orders = orders.filter(completed_at__gte=thirty_days_ago)

        stats['recent_orders'] = recent_orders.count()
        stats['recent_spent'] = recent_orders.aggregate(
            total=Sum('total')
        )['total'] or 0

        # Credit info
        stats['credit_balance'] = customer.get_credit_balance()
        stats['credit_available'] = customer.credit_available

        return stats

    @staticmethod
    def get_top_customers(limit=10, period_days=None):
        """
        Get top customers by spending

        Args:
            limit: Number of customers to return
            period_days: Period in days (None for all time)

        Returns:
            QuerySet of customers
        """
        customers = Customer.objects.filter(is_active=True)

        if period_days:
            from datetime import timedelta
            from django.utils import timezone
            from apps.orders.models import Order

            since = timezone.now() - timedelta(days=period_days)

            # Annotate with period spending
            from django.db.models import Sum, Q
            customers = customers.annotate(
                period_spent=Sum(
                    'orders__total',
                    filter=Q(
                        orders__status='COMPLETED',
                        orders__completed_at__gte=since
                    )
                )
            ).filter(period_spent__gt=0).order_by('-period_spent')
        else:
            # All-time top customers
            customers = customers.filter(
                total_spent__gt=0
            ).order_by('-total_spent')

        return customers[:limit]