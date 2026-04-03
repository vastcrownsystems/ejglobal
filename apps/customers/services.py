from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
import logging
from .models import Customer, CustomerNote, SalesPerson

logger = logging.getLogger(__name__)


class CustomerService:
    """Service for managing customers"""

    @staticmethod
    @transaction.atomic
    def quick_add(full_name, phone="", email="", customer_type="",
                  sales_person_id=None, created_by=None):
        """
        Quick add customer with minimal info

        Used in POS for fast customer creation

        Args:
            full_name: Customer name (required)
            phone: Phone number (optional)
            email: Email (optional)
            customer_type: INDIVIDUAL, RETAILER, or DISTRIBUTOR
            sales_person_id: SalesPerson PK (optional)
            created_by: User creating customer

        Returns:
            Customer instance
        """
        logger.info(f"Quick adding customer {full_name}")

        if not full_name or not full_name.strip():
            raise ValidationError("Customer name is required")

        sales_person = None
        if sales_person_id:
            try:
                sales_person = SalesPerson.objects.get(pk=sales_person_id, is_active=True)
            except SalesPerson.DoesNotExist:
                logger.warning(f"SalesPerson pk={sales_person_id} not found, skipping")

        customer = Customer.objects.create(
            full_name=full_name.strip(),
            phone=phone.strip() if phone else "",
            email=email.strip() if email else "",
            customer_type=customer_type or "INDIVIDUAL",
            sales_person=sales_person,
            created_by=created_by
        )

        logger.info(f"Customer Created: {customer.customer_number}")

        return customer

    @staticmethod
    @transaction.atomic
    def create_customer(full_name, phone="", email="", customer_type="INDIVIDUAL",
                        address_line='', city="", state="", postal_code="",
                        sales_person_id=None,
                        credit_limit=None, credit_terms_days=None, credit_status=None,
                        created_by=None):
        """
        Create customer with full details

        Args:
            full_name: Customer name
            phone: Phone number
            email: Email
            customer_type: INDIVIDUAL, RETAILER, or DISTRIBUTOR
            address_line: Address line
            city: City
            state: State
            postal_code: Postal code
            sales_person_id: SalesPerson PK (optional)
            credit_limit: Credit limit (optional, requires permission)
            credit_terms_days: Payment terms in days (optional)
            credit_status: Credit status (optional)
            created_by: User creating customer

        Returns:
            Customer instance
        """
        logger.info(f"Creating customer: {full_name}")

        if not full_name or not full_name.strip():
            raise ValidationError("Customer name is required")

        sales_person = None
        if sales_person_id:
            try:
                sales_person = SalesPerson.objects.get(pk=sales_person_id, is_active=True)
            except SalesPerson.DoesNotExist:
                logger.warning(f"SalesPerson pk={sales_person_id} not found, skipping")

        customer_data = {
            'full_name': full_name.strip(),
            'phone': phone.strip() if phone else '',
            'email': email.strip() if email else '',
            'customer_type': customer_type or 'INDIVIDUAL',
            'address_line': address_line.strip() if address_line else '',
            'city': city.strip() if city else '',
            'state': state.strip() if state else '',
            'postal_code': postal_code.strip() if postal_code else '',
            'sales_person': sales_person,
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

class SalesPersonService:
    """Service for managing sales persons"""

    @staticmethod
    @transaction.atomic
    def create(full_name, phone="", email="", employee_id=None, user_id=None):
        """
        Create a new sales person.

        Args:
            full_name: Full name (required)
            phone: Phone number (optional)
            email: Email address (optional)
            employee_id: Custom employee ID (optional, auto-generated if blank)
            user_id: Link to auth User PK (optional)

        Returns:
            SalesPerson instance
        """
        logger.info(f"Creating sales person: {full_name}")

        if not full_name or not full_name.strip():
            raise ValidationError("Sales person name is required")

        if email and SalesPerson.objects.filter(user__email=email).exists():
            pass  # email on user, not on sales person directly

        # Validate user link
        user = None
        if user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(pk=user_id, is_active=True)
                if SalesPerson.objects.filter(user=user).exists():
                    raise ValidationError(
                        f"User '{user.username}' is already linked to another sales person"
                    )
            except User.DoesNotExist:
                raise ValidationError(f"User with id={user_id} does not exist")

        # Validate unique employee_id if provided
        if employee_id:
            if SalesPerson.objects.filter(employee_id=employee_id).exists():
                raise ValidationError(f"Employee ID '{employee_id}' is already in use")

        sales_person = SalesPerson.objects.create(
            full_name=full_name.strip(),
            phone=phone.strip() if phone else '',
            email=email.strip() if email else '',
            employee_id=employee_id or None,
            user=user,
            is_active=True,
        )

        logger.info(f"Sales person created: {sales_person.employee_id} - {sales_person.full_name}")

        return sales_person

    @staticmethod
    @transaction.atomic
    def update(sales_person, full_name, phone="", email="",
               employee_id=None, user_id=None, is_active=True):
        """
        Update an existing sales person.

        Args:
            sales_person: SalesPerson instance
            full_name: Full name (required)
            phone: Phone number
            email: Email
            employee_id: Employee ID (optional)
            user_id: Link to auth User PK (optional, pass None to unlink)
            is_active: Active flag

        Returns:
            Updated SalesPerson instance
        """
        logger.info(f"Updating sales person: {sales_person.employee_id}")

        if not full_name or not full_name.strip():
            raise ValidationError("Sales person name is required")

        # Validate user link
        user = None
        if user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(pk=user_id, is_active=True)
                already_linked = (
                    SalesPerson.objects
                    .filter(user=user)
                    .exclude(pk=sales_person.pk)
                    .exists()
                )
                if already_linked:
                    raise ValidationError(
                        f"User '{user.username}' is already linked to another sales person"
                    )
            except User.DoesNotExist:
                raise ValidationError(f"User with id={user_id} does not exist")

        # Validate employee_id uniqueness
        if employee_id:
            conflict = (
                SalesPerson.objects
                .filter(employee_id=employee_id)
                .exclude(pk=sales_person.pk)
                .exists()
            )
            if conflict:
                raise ValidationError(f"Employee ID '{employee_id}' is already in use")

        sales_person.full_name = full_name.strip()
        sales_person.phone = phone.strip() if phone else ''
        sales_person.email = email.strip() if email else ''
        sales_person.employee_id = employee_id or sales_person.employee_id
        sales_person.user = user
        sales_person.is_active = is_active

        sales_person.save()

        logger.info(f"Sales person updated: {sales_person.employee_id}")

        return sales_person

    @staticmethod
    @transaction.atomic
    def deactivate(sales_person):
        """
        Deactivate a sales person.
        Unassigns all their customers (sets sales_person=NULL, preserves customer records).

        Args:
            sales_person: SalesPerson instance

        Returns:
            int — number of customers unassigned
        """
        logger.info(f"Deactivating sales person: {sales_person.employee_id}")

        customer_count = sales_person.customers.count()

        # Unassign all customers
        sales_person.customers.update(sales_person=None)

        # Deactivate
        sales_person.is_active = False
        sales_person.save(update_fields=['is_active'])

        logger.info(
            f"Sales person {sales_person.employee_id} deactivated. "
            f"{customer_count} customers unassigned."
        )

        return customer_count

    @staticmethod
    @transaction.atomic
    def reassign_customers(from_sp, to_sp):
        """
        Move all customers from one sales person to another.

        Args:
            from_sp: Source SalesPerson instance
            to_sp: Target SalesPerson instance

        Returns:
            int — number of customers moved
        """
        if from_sp.pk == to_sp.pk:
            raise ValidationError("Source and target sales person must be different")

        if not to_sp.is_active:
            raise ValidationError(
                f"Cannot reassign to inactive sales person '{to_sp.full_name}'"
            )

        count = from_sp.customers.count()
        from_sp.customers.update(sales_person=to_sp)

        logger.info(
            f"Reassigned {count} customers from {from_sp.employee_id} to {to_sp.employee_id}"
        )

        return count

    @staticmethod
    def assign_customer(sales_person, customer):
        """
        Assign a specific customer to a sales person.

        Args:
            sales_person: SalesPerson instance
            customer: Customer instance
        """
        if not sales_person.is_active:
            raise ValidationError(f"Sales person '{sales_person.full_name}' is not active")

        customer.sales_person = sales_person
        customer.save(update_fields=['sales_person'])

        logger.info(
            f"Customer {customer.customer_number} assigned to {sales_person.employee_id}"
        )

    @staticmethod
    def unassign_customer(customer):
        """
        Remove the sales person assignment from a customer.

        Args:
            customer: Customer instance
        """
        customer.sales_person = None
        customer.save(update_fields=['sales_person'])

        logger.info(f"Sales person unassigned from customer {customer.customer_number}")

    @staticmethod
    def get_performance_summary(sales_person):
        """
        Summarise a sales person's portfolio.

        Returns:
            dict with customer counts, revenue, and credit stats
        """
        from django.db.models import Sum, Count, Avg

        customers = sales_person.customers.filter(is_active=True)

        agg = customers.aggregate(
            total_customers=Count('id'),
            total_revenue=Sum('total_spent'),
            total_orders=Sum('total_orders'),
            avg_order_value=Avg('total_spent'),
        )

        outstanding = sum(c.total_credit_outstanding for c in customers)

        return {
            'total_customers': agg['total_customers'] or 0,
            'total_revenue': agg['total_revenue'] or Decimal('0.00'),
            'total_orders': agg['total_orders'] or 0,
            'avg_order_value': agg['avg_order_value'] or Decimal('0.00'),
            'total_credit_outstanding': outstanding,
            'customer_types': {
                'individual': customers.filter(customer_type='INDIVIDUAL').count(),
                'retailer': customers.filter(customer_type='RETAILER').count(),
                'distributor': customers.filter(customer_type='DISTRIBUTOR').count(),
            }
        }