from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
import logging

from .models import Receipt
from apps.orders.models import Order

logger = logging.getLogger(__name__)


class ReceiptService:
    """Service for generating and managing receipts"""

    @staticmethod
    @transaction.atomic
    def generate_receipt(order):
        """
        Generate receipt for completed order

        Creates a snapshot of the order for permanent record

        Args:
            order: Order instance (must be COMPLETED)

        Returns:
            Receipt instance

        Raises:
            ValidationError: If order not completed
        """
        logger.info(f"Generating receipt for order {order.order_number}")

        # Validate order is completed
        if order.status != 'COMPLETED':
            raise ValidationError(
                f"Cannot generate receipt for {order.get_status_display()} order"
            )

        # Check if receipt already exists
        if hasattr(order, 'receipt'):
            logger.warning(f"Receipt already exists for order {order.order_number}")
            return order.receipt

        # Generate receipt number
        receipt_number = ReceiptService._generate_receipt_number()

        # Create order snapshot
        receipt_data = ReceiptService._create_order_snapshot(order)

        # Create receipt
        receipt = Receipt.objects.create(
            receipt_no=receipt_number,
            order=order,
            payload=receipt_data
        )

        logger.info(f"Receipt generated: {receipt.receipt_no}")

        return receipt

    @staticmethod
    def _generate_receipt_number():
        """
        Generate unique receipt number

        Format: RCP-YYYYMMDD-NNNN
        """
        today = timezone.now().date()
        date_str = today.strftime('%Y%m%d')
        prefix = f"RCP-{date_str}-"

        with transaction.atomic():
            count = Receipt.objects.filter(
                receipt_no__startswith=prefix
            ).count()

            sequence = count + 1
            receipt_number = f"{prefix}{sequence:04d}"

            # Safety loop (extremely rare but good practice)
            while Receipt.objects.filter(receipt_no=receipt_number).exists():
                sequence += 1
                receipt_number = f"{prefix}{sequence:04d}"

            return receipt_number

    @staticmethod
    def _create_order_snapshot(order):
        """
        Create complete snapshot of order for receipt.

        Captures customer FK data, cashier, session, items, payments and
        totals at the exact moment of sale so the receipt is immutable even
        if related records change later.

        Args:
            order: Order instance (select_related before calling for efficiency)

        Returns:
            dict: Full order snapshot stored in Receipt.payload
        """
        # ── Customer ─────────────────────────────────────────────────────
        # Priority: linked FK customer → flat denormalised fields → walk-in
        customer = order.customer  # FK (may be None)

        if customer:
            customer_data = {
                'id':             customer.pk,
                'name':           customer.full_name,
                'email':          customer.email          or '',
                'phone':          customer.phone          or '',
                'customer_number': customer.customer_number or '',
                'customer_type':  getattr(customer, 'customer_type', ''),
                'address':        getattr(customer, 'address', '') or '',
                'notes':          getattr(customer, 'notes', '')   or '',
                'is_walk_in':     False,
            }
        else:
            # Fall back to denormalised fields stored on the order itself
            customer_data = {
                'id':             None,
                'name':           getattr(order, 'customer_name',  None) or 'Walk-in Customer',
                'email':          getattr(order, 'customer_email', None) or '',
                'phone':          getattr(order, 'customer_phone', None) or '',
                'customer_number': '',
                'customer_type':  '',
                'address':        '',
                'notes':          '',
                'is_walk_in':     True,
            }

        # ── Cashier ───────────────────────────────────────────────────────
        cashier = order.created_by
        cashier_data = {
            'id':         cashier.pk,
            'name':       cashier.get_full_name() or cashier.username,
            'username':   cashier.username,
            'email':      cashier.email or '',
        }

        # ── Session ───────────────────────────────────────────────────────
        session_data = None
        if order.cashier_session:
            s = order.cashier_session
            session_data = {
                'id':            s.pk,
                'register_name': getattr(s.register, 'name', '') if hasattr(s, 'register') else '',
                'store_name':    getattr(s.store,    'name', '') if hasattr(s, 'store')    else '',
                'opened_at':     s.opened_at.isoformat() if hasattr(s, 'opened_at') else '',
            }

        # ── Items ─────────────────────────────────────────────────────────
        items = []
        for item in order.items.select_related('variant', 'variant__product').all():
            items.append({
                'id':               item.pk,
                'product_name':     item.product_name,
                'variant_name':     item.variant_name or item.product_name,
                'display_name':     (
                    f"{item.product_name} — {item.variant_name}"
                    if item.variant_name and item.variant_name != item.product_name
                    else item.product_name
                ),
                'sku':              item.sku or '',
                'quantity':         float(item.quantity),
                'unit_price':       float(item.unit_price),
                'discount_amount':  float(item.discount_amount),
                'line_total':       float(item.line_total),
            })

        # ── Payments ──────────────────────────────────────────────────────
        payments = []
        for payment in order.order_payments.all():
            payments.append({
                'id':               payment.pk,
                'amount':           float(payment.amount),
                'payment_method':   payment.payment_method,
                'payment_method_display': payment.get_payment_method_display(),
                'reference_number': payment.reference_number or '',
                'created_at':       payment.created_at.isoformat(),
            })

        # ── Totals ────────────────────────────────────────────────────────
        totals = {
            'subtotal':        float(order.subtotal),
            'discount_amount': float(order.discount_amount),
            'tax_amount':      float(order.tax_amount),
            'total':           float(order.total),
            'paid_amount':     float(order.amount_paid),
            'balance_due':     float(order.balance_due),
            'item_count':      order.item_count,
        }

        # ── Full snapshot ─────────────────────────────────────────────────
        snapshot = {
            'order': {
                'id':            order.pk,
                'order_number':  order.order_number,
                'status':        order.status,
                'status_display': order.get_status_display(),
                'created_at':    order.created_at.isoformat(),
                'completed_at':  order.completed_at.isoformat() if order.completed_at else None,
                'notes':         order.notes or '',
            },
            'customer':  customer_data,
            'cashier':   cashier_data,
            'session':   session_data,
            'items':     items,
            'payments':  payments,
            'totals':    totals,
            'metadata': {
                'generated_at': timezone.now().isoformat(),
                'system':       'EJ Global POS',
                'version':      '1.0',
            },
        }

        return snapshot

    @staticmethod
    def get_receipt_by_number(receipt_number):
        """
        Get receipt by receipt number

        Args:
            receipt_number: Receipt number string

        Returns:
            Receipt instance or None
        """
        try:
            return Receipt.objects.select_related(
                'order',
                'issued_by',
                'cashier_session'
            ).get(receipt_no=receipt_number)
        except Receipt.DoesNotExist:
            return None

    @staticmethod
    def get_receipts_for_session(cashier_session):
        """
        Get all receipts for a cashier session

        Args:
            cashier_session: CashierSession instance

        Returns:
            QuerySet of Receipts
        """
        return Receipt.objects.filter(
            cashier_session=cashier_session
        ).select_related('order', 'issued_by').order_by('-issued_at')

    @staticmethod
    def get_daily_receipts(date=None):
        """
        Get receipts for a specific date

        Args:
            date: Date to filter (default: today)

        Returns:
            QuerySet of Receipts
        """
        if date is None:
            date = timezone.now().date()

        return Receipt.objects.filter(
            issued_at__date=date
        ).select_related('order', 'issued_by').order_by('-issued_at')