# apps/credit/services.py
"""
Credit Ledger Service - Business logic for AR management
"""
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Q, F, Count
from .models import CreditLedger, CreditPayment


class CreditLedgerService:
    """
    Service for managing credit ledger operations
    """

    @staticmethod
    @transaction.atomic
    def create_credit_sale(order, terms_days=None, due_date=None, created_by=None):
        """
        Create credit ledger entry for a credit sale

        Args:
            order: Order instance
            terms_days: Payment terms in days (default: customer's terms or 30)
            due_date: Specific due date (optional, overrides terms_days)
            created_by: User creating the entry

        Returns:
            CreditLedger instance

        Raises:
            ValueError: If customer is missing or credit limit exceeded
        """
        if not order.customer:
            raise ValueError("Credit sales require a customer")

        customer = order.customer

        # Check credit limit
        if not customer.can_extend_credit(order.total):
            raise ValueError(
                f"Credit limit exceeded. "
                f"Available: ₦{customer.available_credit:,.2f}, "
                f"Requested: ₦{order.total:,.2f}"
            )

        # Determine payment terms
        if not terms_days:
            terms_days = customer.credit_terms_days or 30

        # Calculate due date
        if not due_date:
            due_date = timezone.now().date() + timedelta(days=terms_days)

        # Create ledger entry
        ledger = CreditLedger.objects.create(
            customer=customer,
            order=order,
            transaction_type='SALE',
            total_amount=order.total,
            balance_outstanding=order.total,
            due_date=due_date,
            terms_days=terms_days,
            created_by=created_by or order.created_by,
            notes=f'Credit sale from order {order.order_number}'
        )

        # Update order
        order.sale_type = 'CREDIT'
        order.credit_terms_days = terms_days
        order.credit_due_date = due_date
        order.save(update_fields=['sale_type', 'credit_terms_days', 'credit_due_date'])

        return ledger

    @staticmethod
    @transaction.atomic
    def record_payment(ledger, amount, payment_method, user,
                       reference='', notes='', cashier_session=None):
        """
        Record a payment against a credit ledger entry

        Args:
            ledger: CreditLedger instance
            amount: Payment amount
            payment_method: Payment method (CASH, CARD, etc.)
            user: User receiving payment
            reference: Payment reference number
            notes: Additional notes
            cashier_session: Optional cashier session

        Returns:
            CreditPayment instance

        Raises:
            ValueError: If amount is invalid or exceeds balance
        """
        # Validate amount
        if amount <= 0:
            raise ValueError("Payment amount must be positive")

        if amount > ledger.balance_outstanding:
            raise ValueError(
                f"Payment amount (₦{amount:,.2f}) exceeds "
                f"outstanding balance (₦{ledger.balance_outstanding:,.2f})"
            )

        # Create payment record
        payment = CreditPayment.objects.create(
            ledger=ledger,
            customer=ledger.customer,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference,
            notes=notes,
            received_by=user,
            cashier_session=cashier_session
        )

        return payment

    @staticmethod
    def get_customer_statement(customer, start_date=None, end_date=None):
        """
        Generate customer statement of account

        Args:
            customer: Customer instance
            start_date: Statement start date
            end_date: Statement end date

        Returns:
            dict: Statement details with entries and totals
        """
        entries = customer.credit_ledger_entries.all()

        # Filter by date range
        if start_date:
            entries = entries.filter(transaction_date__date__gte=start_date)
        if end_date:
            entries = entries.filter(transaction_date__date__lte=end_date)

        # Calculate opening balance (before start_date)
        opening_balance = Decimal('0.00')
        if start_date:
            opening_entries = customer.credit_ledger_entries.filter(
                transaction_date__date__lt=start_date,
                transaction_type='SALE'
            )
            opening_balance = opening_entries.aggregate(
                total=Sum('balance_outstanding')
            )['total'] or Decimal('0.00')

        # Calculate totals for period
        sales = entries.filter(
            transaction_type='SALE'
        ).aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0.00')

        payments_data = CreditPayment.objects.filter(
            ledger__in=entries.filter(transaction_type='SALE')
        )

        if start_date:
            payments_data = payments_data.filter(payment_date__date__gte=start_date)
        if end_date:
            payments_data = payments_data.filter(payment_date__date__lte=end_date)

        payments = payments_data.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        closing_balance = opening_balance + sales - payments

        return {
            'customer': customer,
            'entries': entries.select_related('order', 'created_by').prefetch_related('payments'),
            'opening_balance': opening_balance,
            'total_sales': sales,
            'total_payments': payments,
            'closing_balance': closing_balance,
            'start_date': start_date,
            'end_date': end_date,
        }

    @staticmethod
    def get_aging_report(as_of_date=None):
        """
        Generate accounts receivable aging report

        Args:
            as_of_date: Date to calculate aging from (default: today)

        Returns:
            dict: Aging buckets with totals
        """
        if not as_of_date:
            as_of_date = timezone.now().date()

        unpaid_ledgers = CreditLedger.objects.filter(
            balance_outstanding__gt=0,
            transaction_type='SALE'
        )

        aging = {
            'current': Decimal('0.00'),  # 0-30 days
            'days_31_60': Decimal('0.00'),  # 31-60 days
            'days_61_90': Decimal('0.00'),  # 61-90 days
            'over_90': Decimal('0.00'),  # 90+ days
            'total': Decimal('0.00'),
        }

        for ledger in unpaid_ledgers:
            days_old = (as_of_date - ledger.transaction_date.date()).days

            if days_old <= 30:
                aging['current'] += ledger.balance_outstanding
            elif days_old <= 60:
                aging['days_31_60'] += ledger.balance_outstanding
            elif days_old <= 90:
                aging['days_61_90'] += ledger.balance_outstanding
            else:
                aging['over_90'] += ledger.balance_outstanding

        aging['total'] = sum([
            aging['current'],
            aging['days_31_60'],
            aging['days_61_90'],
            aging['over_90']
        ])

        return aging

    @staticmethod
    def get_overdue_customers():
        """
        Get list of customers with overdue balances

        Returns:
            QuerySet: Customers with overdue amounts
        """
        from apps.customers.models import Customer

        return Customer.objects.filter(
            credit_ledger_entries__status='OVERDUE',
            credit_ledger_entries__balance_outstanding__gt=0
        ).distinct().annotate(
            overdue_amount=Sum(
                'credit_ledger_entries__balance_outstanding',
                filter=Q(credit_ledger_entries__status='OVERDUE')
            ),
            overdue_count=Count(
                'credit_ledger_entries',
                filter=Q(credit_ledger_entries__status='OVERDUE')
            )
        ).order_by('-overdue_amount')

    @staticmethod
    def get_collection_summary(start_date=None, end_date=None):
        """
        Get summary of credit payments collected

        Args:
            start_date: Start date for summary
            end_date: End date for summary

        Returns:
            dict: Collection summary with breakdowns
        """
        payments = CreditPayment.objects.all()

        if start_date:
            payments = payments.filter(payment_date__date__gte=start_date)
        if end_date:
            payments = payments.filter(payment_date__date__lte=end_date)

        # Total collected
        total_collected = payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        # By payment method
        by_method = payments.values(
            'payment_method'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')

        # By day
        by_day = payments.values(
            'payment_date__date'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-payment_date__date')

        # By cashier
        by_cashier = payments.values(
            'received_by__username'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')

        return {
            'total_collected': total_collected,
            'payment_count': payments.count(),
            'by_method': by_method,
            'by_day': by_day,
            'by_cashier': by_cashier,
            'start_date': start_date,
            'end_date': end_date,
        }

    @staticmethod
    def update_overdue_statuses():
        """
        Update status for all overdue ledger entries
        Run this as a scheduled task daily

        Returns:
            int: Number of entries updated
        """
        today = timezone.now().date()

        overdue_entries = CreditLedger.objects.filter(
            due_date__lt=today,
            balance_outstanding__gt=0,
            status__in=['PENDING', 'PARTIAL']
        )

        count = overdue_entries.update(status='OVERDUE')

        return count