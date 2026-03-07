from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
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
            customer_type=customer_type or "INDIVIDUAL",
            created_by=created_by
        )

        logger.info(f"Customer Created: {customer.customer_number}")

        return customer

    @staticmethod
    @transaction.atomic
    def create_customer(full_name, phone="", email="", customer_type="INDIVIDUAL",
                        address_line='', city="", state="", postal_code="",
                        credit_limit=None, credit_terms_days=None, credit_status=None,
                        created_by=None):
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
            credit_limit: Credit limit (optional, requires permission)
            credit_terms_days: Payment terms in days (optional)
            credit_status: Credit status (optional)
            created_by: User creating customer

        Returns:
            Customer instance
        """
        logger.info(f"Creating customer: {full_name}")

        # Validate
        if not full_name or not full_name.strip():
            raise ValidationError("Customer name is required")

        # Prepare customer data
        customer_data = {
            'full_name': full_name.strip(),
            'phone': phone.strip() if phone else '',
            'email': email.strip() if email else '',
            'customer_type': customer_type or 'INDIVIDUAL',
            'address_line': address_line.strip() if address_line else '',
            'city': city.strip() if city else '',
            'state': state.strip() if state else '',
            'postal_code': postal_code.strip() if postal_code else '',
            'created_by': created_by
        }

        # Add credit fields if provided
        if credit_limit is not None:
            try:
                customer_data['credit_limit'] = Decimal(str(credit_limit))
            except (ValueError, TypeError):
                logger.warning(f"Invalid credit_limit value: {credit_limit}, using default")
                customer_data['credit_limit'] = Decimal('0.00')

        if credit_terms_days is not None:
            try:
                customer_data['credit_terms_days'] = int(credit_terms_days)
            except (ValueError, TypeError):
                logger.warning(f"Invalid credit_terms_days value: {credit_terms_days}, using default")
                customer_data['credit_terms_days'] = 30

        if credit_status:
            if credit_status in ['APPROVED', 'SUSPENDED', 'BLOCKED']:
                customer_data['credit_status'] = credit_status
            else:
                logger.warning(f"Invalid credit_status value: {credit_status}, using default")

        # Create customer
        customer = Customer.objects.create(**customer_data)

        logger.info(f"Customer created: {customer.customer_number}")

        return customer

    @staticmethod
    @transaction.atomic
    def update_credit_limit(customer, credit_limit, credit_terms_days=None,
                            credit_status=None, updated_by=None):
        """
        Update customer credit settings

        Args:
            customer: Customer instance
            credit_limit: New credit limit
            credit_terms_days: Payment terms in days (optional)
            credit_status: Credit status (optional)
            updated_by: User making the update

        Returns:
            Updated customer instance
        """
        logger.info(f"Updating credit for customer {customer.customer_number}")

        # Validate credit limit
        try:
            new_limit = Decimal(str(credit_limit))
            if new_limit < 0:
                raise ValidationError("Credit limit cannot be negative")
        except (ValueError, TypeError):
            raise ValidationError("Invalid credit limit value")

        # Check if new limit is below outstanding balance
        if new_limit < customer.total_credit_outstanding:
            logger.warning(
                f"Credit limit (₦{new_limit}) is less than outstanding balance "
                f"(₦{customer.total_credit_outstanding}) for {customer.customer_number}"
            )

        # Update fields
        customer.credit_limit = new_limit

        if credit_terms_days is not None:
            try:
                customer.credit_terms_days = int(credit_terms_days)
            except (ValueError, TypeError):
                raise ValidationError("Invalid credit terms days value")

        if credit_status:
            if credit_status not in ['APPROVED', 'SUSPENDED', 'BLOCKED']:
                raise ValidationError("Invalid credit status")
            customer.credit_status = credit_status

        customer.save(update_fields=['credit_limit', 'credit_terms_days', 'credit_status'])

        # Add audit note
        if updated_by:
            CustomerService.add_note(
                customer=customer,
                note_text=f"Credit limit updated to ₦{new_limit}. "
                          f"Terms: {customer.credit_terms_days} days. "
                          f"Status: {customer.credit_status}",
                note_type='CREDIT',
                created_by=updated_by
            )

        logger.info(f"Credit updated for {customer.customer_number}")

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
        stats['outstanding_balance'] = customer.outstanding_balance
        stats['credit_limit'] = customer.credit_limit
        stats['available_credit'] = customer.available_credit
        stats['credit_status'] = customer.credit_status

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

    @staticmethod
    def get_customers_with_credit(status=None):
        """
        Get customers with credit limits

        Args:
            status: Filter by credit status (optional)

        Returns:
            QuerySet of customers
        """
        customers = Customer.objects.filter(
            is_active=True,
            credit_limit__gt=0
        )

        if status:
            customers = customers.filter(credit_status=status)

        return customers.order_by('-total_credit_outstanding')

    @staticmethod
    def check_credit_eligibility(customer, amount):
        """
        Check if customer is eligible for credit purchase

        Args:
            customer: Customer instance
            amount: Purchase amount

        Returns:
            tuple (eligible: bool, message: str)
        """
        # Check credit status
        if customer.credit_status == 'BLOCKED':
            return False, "Customer credit is blocked"

        if customer.credit_status == 'SUSPENDED':
            return False, "Customer credit is suspended"

        # Check if credit limit is set
        if customer.credit_limit <= 0:
            return False, "Customer does not have a credit limit"

        # Check available credit
        available = customer.available_credit

        if amount > available:
            return False, f"Insufficient credit. Available: ₦{available}, Required: ₦{amount}"

        return True, "Credit approved"