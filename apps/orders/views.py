from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.sales.models import CashierSession
from apps.catalog.models import ProductVariant, Product
from apps.orders.models import Order, OrderItem, OrderPayment
from apps.orders.services import OrderService
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django.db.models import Count
from decimal import Decimal, InvalidOperation
from django.db.models import Sum
from collections import defaultdict
from datetime import datetime, timedelta
from apps.receipts.services import ReceiptService


import logging
logger = logging.getLogger(__name__)
User = get_user_model()

# -----------------------------
# Session helpers
# -----------------------------
def get_open_session(user):
    return (
        CashierSession.objects
        .filter(cashier=user, closed_at__isnull=True)
        .select_related("register", "store")
        .first()
    )


def require_open_session(user):
    session = get_open_session(user)
    if not session:
        raise ValidationError("No open cashier session. Start a session first.")
    return session


# -----------------------------
# Cart helpers (single source of truth)
# -----------------------------
def get_or_create_cart(session, user):
    cart = (
        Order.objects
        .filter(cashier_session=session, created_by=user, status="DRAFT")
        .first()
    )
    if cart:
        return cart

    return Order.objects.create(
        cashier_session=session,
        created_by=user,
        status="DRAFT",
        payment_status="UNPAID",
        subtotal=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        total=Decimal("0.00"),
        amount_paid=Decimal("0.00"),
    )


def fetch_cart(cart_id) -> Order:
    """
    Always fetch cart with items and variants to render reliably.
    """
    return (
        Order.objects
        .filter(pk=cart_id)
        .prefetch_related("items__variant", "items__variant__product")
        .first()
    )


def cart_context(cart: Order):
    cart = fetch_cart(cart.pk)
    items = cart.items.all()
    return {"order": cart, "items": items}


# -----------------------------
# POS screen
# -----------------------------
@login_required
@require_http_methods(["GET"])
def pos_screen(request):
    try:
        session = require_open_session(request.user)
    except ValidationError:
        messages.error(request, "No open cashier session. Start a session first.")
        return redirect("sales:start_session")

    order_id = request.session.get("current_order_id")
    cart = None

    if order_id:
        cart = Order.objects.filter(
            pk=order_id,
            status="DRAFT",
            cashier_session=session,
            created_by=request.user
        ).first()

    if not cart:
        cart = get_or_create_cart(session, request.user)
        request.session["current_order_id"] = cart.id
        request.session.modified = True

    cart = fetch_cart(cart.pk)


    products = (
        Product.objects
        .prefetch_related("variants")
        .filter(is_active=True)
    )

    variants = (
        ProductVariant.objects
        .select_related("product")
        .filter(is_active=True, product__is_active=True)
        .order_by("product__name", "name")
    )

    held_count = get_held_orders_count(request.user)

    context = {
        "session": session,
        "products": products,
        "variants": variants,
        'held_count': held_count,
        **cart_context(cart),  # This should now show the items
    }

    return render(request, "orders/pos.html", context)


@require_http_methods(["POST"])
@login_required
@transaction.atomic
def cart_add(request, variant_id):
    session = CashierSession.objects.filter(
        cashier=request.user, closed_at__isnull=True
    ).first()
    if not session:
        return HttpResponseBadRequest("No open cashier session.")

    cart = get_or_create_cart(session, request.user)
    request.session['current_order_id'] = cart.id
    request.session.modified = True

    try:
        OrderService.add_item(cart, variant_id, quantity=1)
    except ValidationError as e:
        return HttpResponseBadRequest(str(e))

    cart = fetch_cart(cart.pk)               # ✅ re-fetch truth
    items = cart.items.all()                 # ✅ correct related_name

    return render(request, "orders/partials/cart_panel.html", {"order": cart, "items": items})



# -----------------------------
# Update quantity (HTMX)
# -----------------------------
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def cart_update_qty(request, item_id):
    session = get_open_session(request.user)
    if not session:
        return HttpResponseBadRequest("No open cashier session.")

    cart = get_or_create_cart(session, request.user)
    request.session['current_order_id'] = cart.id
    request.session.modified = True

    item = get_object_or_404(OrderItem, pk=item_id, order=cart)

    try:
        qty = int(request.POST.get("quantity", "1"))
        if qty < 1:
            return HttpResponseBadRequest("Quantity must be at least 1.")
    except ValueError:
        return HttpResponseBadRequest("Invalid quantity.")

    item.quantity = qty
    item.save()

    # Recalculate totals
    OrderService._recalculate_totals(cart)

    return render(request, "orders/partials/cart_panel.html", cart_context(cart))


# -----------------------------
# Remove line (HTMX)
# -----------------------------
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def cart_remove_line(request, item_id):
    session = get_open_session(request.user)
    if not session:
        return HttpResponseBadRequest("No open cashier session.")

    cart = get_or_create_cart(session, request.user)
    request.session['current_order_id'] = cart.id
    request.session.modified = True

    item = get_object_or_404(OrderItem, pk=item_id, order=cart)
    item.delete()

    OrderService._recalculate_totals(cart)

    return render(request, "orders/partials/cart_panel.html", cart_context(cart))


# -----------------------------
# Clear cart (HTMX)
# -----------------------------
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def cart_clear(request):
    session = get_open_session(request.user)
    if not session:
        return HttpResponseBadRequest("No open cashier session.")

    order_id = request.session.get('current_order_id')
    if not order_id:
        return HttpResponseBadRequest("No active cart.")

    cart = get_object_or_404(
        Order,
        pk=order_id,
        status='DRAFT',
        created_by=request.user,
        cashier_session=session
    )

    cart.items.all().delete()
    OrderService._recalculate_totals(cart)

    return render(request, "orders/partials/cart_panel.html", cart_context(cart))


# -----------------------------
# Checkout
# -----------------------------
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def checkout(request):
    session = get_open_session(request.user)
    if not session:
        return HttpResponseBadRequest("No open cashier session.")

    cart = get_or_create_cart(session, request.user)
    cart = fetch_cart(cart.pk)

    if cart.items.count() == 0:
        return HttpResponseBadRequest("Cart is empty.")

    # Minimal checkout (MVP): confirm order
    cart.status = "CONFIRMED"
    cart.save(update_fields=["status"])

    # After checkout, create fresh cart automatically on next POS load
    return redirect("orders:pos")


@login_required
def cart_apply_item_discount(request, item_id):
    """
    Apply discount to a specific cart item
    """
    if request.method != 'POST':
        return redirect('orders:pos')

    try:
        session = require_open_session(request.user)
    except ValidationError:
        return redirect('sales:start_session')

    # Get cart
    cart = get_or_create_cart(session, request.user)

    # Get discount amount from form input
    # The input name is discount-input-{item_id}
    discount_key = f'discount-input-{item_id}'
    discount_input = request.POST.get(discount_key, '0')

    try:
        discount_amount = Decimal(discount_input.strip())
        if discount_amount < 0:
            discount_amount = Decimal('0')
    except (ValueError, InvalidOperation, AttributeError):
        discount_amount = Decimal('0')

    # Get the item
    try:
        item = OrderItem.objects.get(id=item_id, order=cart)
    except OrderItem.DoesNotExist:
        context = cart_context(cart)
        context['message'] = 'Item not found in cart'
        context['message_type'] = 'error'
        return render(request, 'orders/partials/cart_panel.html', context)

    # Validate discount doesn't exceed item subtotal
    item_subtotal = item.unit_price * item.quantity

    if discount_amount > item_subtotal:
        context = cart_context(cart)
        context['message'] = f'Discount (₦{discount_amount}) cannot exceed item total (₦{item_subtotal})'
        context['message_type'] = 'error'
        return render(request, 'orders/partials/cart_panel.html', context)

    # Apply discount to item
    item.discount_amount = discount_amount
    item.save()  # This will recalculate line_total automatically via model.save()

    # Recalculate order totals
    OrderService._recalculate_totals(cart)

    # Refresh cart to get updated totals
    cart.refresh_from_db()

    # Return updated cart
    context = cart_context(cart)
    if discount_amount > 0:
        context['message'] = f'Discount of ₦{discount_amount} applied to {item.product_name}'
        context['message_type'] = 'success'
    else:
        context['message'] = f'Discount removed from {item.product_name}'
        context['message_type'] = 'info'

    return render(request, 'orders/partials/cart_panel.html', context)

@require_POST
@login_required
@transaction.atomic
def cart_apply_discount(request):
    """
    Apply cart-wide discount

    URL: POST /orders/cart/discount/
    Returns: Full cart HTML
    """
    try:
        order_id = request.session.get('current_order_id')

        if not order_id:
            return HttpResponse('<div class="error">No active cart</div>', status=400)

        order = Order.objects.get(pk=order_id, status='DRAFT', created_by=request.user)

        # Get discount
        discount_type = request.POST.get('discount_type', 'percentage')
        discount_value = Decimal(request.POST.get('discount_value', '0'))

        if discount_type == 'percentage':
            if discount_value < 0 or discount_value > 100:
                raise ValueError("Discount percentage must be between 0 and 100")
            order.discount_percentage = discount_value
        else:
            if discount_value < 0:
                raise ValueError("Discount amount cannot be negative")
            order.discount_amount = discount_value

        order.recalculate_totals()
        order.save()

        logger.info(f"Cart discount applied: {discount_value} ({discount_type})")

        items = order.items.select_related('variant', 'variant__product').all()

        return render(request, 'orders/partials/cart_panel.html', {
            'order': order,
            'items': items,
            'message': 'Discount applied',
            'message_type': 'success'
        })

    except Exception as e:
        logger.exception(f"Error applying discount: {e}")
        return HttpResponse(
            f'<div class="cart-alert cart-alert-error">Error: {str(e)}</div>',
            status=400
        )


@login_required
@require_http_methods(["GET"])
def cart_totals(request):
    """
    Get updated cart totals only

    URL: GET /orders/cart/totals/
    """
    order_id = request.session.get('current_order_id')

    if not order_id:
        return HttpResponse('<div></div>')

    try:
        order = Order.objects.get(pk=order_id, status='DRAFT')
        items = order.items.all()

        return render(request, 'orders/partials/cart_totals.html', {
            'order': order,
            'items': items
        })
    except Order.DoesNotExist:
        return HttpResponse('<div></div>')


@login_required
@require_http_methods(["GET"])
def cart_badge(request):
    """
    Get updated cart badge count

    URL: GET /orders/cart/badge/
    """
    order_id = request.session.get('current_order_id')

    if not order_id:
        return HttpResponse('0')

    try:
        order = Order.objects.get(pk=order_id, status='DRAFT')
        count = order.items.count()
        return HttpResponse(str(count))
    except Order.DoesNotExist:
        return HttpResponse('0')


# ===== CHECKOUT =====

@login_required
@require_http_methods(["GET"])
def checkout_modal(request):
    """
    Load checkout modal

    URL: GET /orders/checkout/
    Returns: Checkout modal HTML
    """
    order_id = request.session.get('current_order_id')

    if not order_id:
        return HttpResponse("")

    try:
        order = Order.objects.select_related("customer").prefetch_related("items", "order_payments").get(
            pk=order_id,
            status='DRAFT',
            created_by=request.user
        )
    except Order.DoesNotExist:
        return HttpResponse('<div class="alert-error">Order not found</div>')

    payments = order.order_payments.all().order_by('-created_at')

    context = {
        'order': order,
        'payments': payments,
        'balance_due': order.balance_due,
        'payment_methods': OrderPayment.PAYMENT_METHODS,
    }

    return render(request, 'orders/checkout_modal.html', context)


@login_required
@require_http_methods(["POST"])
def add_payment(request):
    """
    Add payment to order - handles CREDIT as payment method
    """
    order_id = request.session.get('current_order_id')

    if not order_id:
        return JsonResponse({'error': 'No active order'}, status=400)

    try:
        order = Order.objects.select_for_update().get(
            pk=order_id,
            status='DRAFT',
            created_by=request.user
        )

        payment_method = request.POST.get('payment_method', 'CASH')

        # ✅ CREDIT METHOD - Use full order total as amount
        if payment_method == 'CREDIT':
            # Must have customer for credit
            if not order.customer:
                return render(request, 'orders/partials/payment_summary.html', {
                    'order': order,
                    'payments': order.order_payments.all(),
                    'balance_due': order.balance_due,
                    'message': '❌ Customer required for credit sales',
                    'message_type': 'error'
                })

            # Use full order total
            amount = order.total
            reference = f'CREDIT-{order.order_number}'
            notes = 'Credit sale - Payment deferred'
        else:
            # Normal payment
            amount = Decimal(request.POST.get('amount', '0'))
            reference = request.POST.get('reference', '').strip()
            notes = request.POST.get('notes', '').strip()

        # Add payment
        payment = OrderService.add_payment(
            order=order,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference,
            notes=notes,
            user=request.user
        )

        order.refresh_from_db()

        payments = order.order_payments.all().order_by('-created_at')

        # ✅ Different message for credit
        if payment_method == 'CREDIT':
            message = f'✅ Credit sale registered - Balance: ₦{order.total}'
        else:
            message = f'✅ Payment of ₦{amount} added'

        context = {
            'order': order,
            'payments': payments,
            'balance_due': order.balance_due,
            'message': message,
            'message_type': 'success'
        }

        return render(request, 'orders/partials/payment_summary.html', context)

    except Exception as e:
        logger.exception(f"Error adding payment: {e}")
        return render(request, 'orders/partials/payment_summary.html', {
            'order': order,
            'payments': order.order_payments.all(),
            'balance_due': order.balance_due,
            'message': f'❌ Error: {str(e)}',
            'message_type': 'error'
        })


@login_required
@require_http_methods(["POST"])
def complete_sale(request):
    """
    Complete sale - handles both paid and credit sales
    """
    order_id = request.session.get("current_order_id")

    if not order_id:
        messages.error(request, "No active order")
        return redirect("orders:pos")

    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(
                pk=order_id,
                status="DRAFT",
                created_by=request.user
            )

            if not order.items.exists():
                raise ValueError("Cannot complete empty order")

            # Check if has credit payment
            has_credit_payment = order.order_payments.filter(
                payment_method='CREDIT'
            ).exists()

            if has_credit_payment:
                # Credit sale - must have customer
                if not order.customer:
                    raise ValueError("Credit sales require a customer")
            else:
                # Normal sale - must be fully paid
                order.update_payment_status()
                if order.balance_due > 0:
                    raise ValueError(
                        f"Order not fully paid. Balance: ₦{order.balance_due}"
                    )

            # Confirm order and reduce stock
            OrderService.confirm_order(order, reduce_stock=True)

            # Mark as completed
            order.status = "COMPLETED"
            order.completed_at = timezone.now()
            order.save(update_fields=["status", "completed_at"])

            # Update payment status
            order.update_payment_status()

            # Generate receipt
            from apps.receipts.services import ReceiptService
            receipt = ReceiptService.generate_receipt(order)

            # Clear session
            request.session.pop("current_order_id", None)

            # Render receipt modal
            html = render_to_string(
                "receipts/receipt_modal.html",
                {
                    "receipt": receipt,
                    "data": receipt.payload,
                },
                request=request
            )

            response = HttpResponse(html)
            # ✅ DON'T send HX-Trigger - let receipt stay open
            # response["HX-Trigger"] = "saleCompleted"  # ❌ This causes immediate redirect

            return response

    except Exception as e:
        logger.exception(f"Error completing sale: {e}")
        messages.error(request, f"❌ Error: {str(e)}")
        return redirect("orders:pos")


@login_required
@require_http_methods(["POST"])
def quick_checkout(request):
    """
    Quick checkout with single payment

    URL: POST /orders/checkout/quick/
    Returns: JSON response
    """
    order_id = request.session.get('current_order_id')

    if not order_id:
        return JsonResponse({'error': 'No active order'}, status=400)

    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order_id, status='DRAFT')

            amount = Decimal(request.POST.get('amount', str(order.total)))
            payment_method = request.POST.get('payment_method', 'CASH')

            OrderService.add_payment(
                order=order,
                amount=amount,
                payment_method=payment_method,
                user=request.user
            )

            order.refresh_from_db()

            if order.is_paid:
                OrderService.confirm_order(order, reduce_stock=True)
                order.complete()

                from apps.receipts.services import ReceiptService
                receipt = ReceiptService.generate_receipt(order)

                if 'current_order_id' in request.session:
                    del request.session['current_order_id']
                    request.session.modified = True

                return JsonResponse({
                    'success': True,
                    'receipt_url': f'/receipts/{receipt.id}/',
                    'message': 'Sale completed'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'balance_due': float(order.balance_due),
                    'message': f'Balance: ₦{order.balance_due}'
                })

    except Exception as e:
        logger.exception(f"Quick checkout error: {e}")
        return JsonResponse({'error': str(e)}, status=400)


# ==================== HOLD/DRAFT ORDER VIEWS ====================

@login_required
@require_POST
@transaction.atomic
def hold_current_order(request):
    """
    Hold the current draft order
    Saves it with customer info and notes, marks as HELD, clears session cart
    """

    order_id = request.session.get('current_order_id')
    if not order_id:
        messages.error(request, "No active order to hold")
        return redirect('orders:pos')

    try:
        order = Order.objects.get(
            id=order_id,
            status='DRAFT',
            created_by=request.user
        )
    except Order.DoesNotExist:
        messages.error(request, "Order not found")
        request.session.pop('current_order_id', None)
        return redirect('orders:pos')

    # Prevent holding empty order
    if order.items.count() == 0:
        messages.error(request, "Cannot hold an empty order")
        return redirect('orders:pos')

    # Update customer info
    customer_name = request.POST.get('customer_name', '').strip()
    notes = request.POST.get('notes', '').strip()

    if customer_name:
        order.customer_name = customer_name

    if notes:
        order.notes = notes

    order.status = 'HELD'

    order.save()

    # Clear session
    request.session.pop('current_order_id', None)
    request.session.modified = True

    messages.success(
        request,
        f"Order {order.order_number} has been held successfully."
    )

    return redirect('orders:pos')


@login_required
def draft_orders_list(request):
    """
    Display all held orders (draft orders)
    For managers: show all held orders
    For cashiers: show only their held orders
    """
    # Check if user is manager
    is_manager = request.user.groups.filter(name__in=['Admin', 'Manager']).exists()

    # Get draft orders with items
    if is_manager:
        # Managers see all held orders
        draft_orders = Order.objects.filter(status='HELD').annotate(
            item_count_check=Count('items')
        ).filter(
            item_count_check__gt=0  # Only orders with items
        ).select_related(
            'customer', 'created_by', 'cashier_session'
        ).prefetch_related('items').order_by('-created_at')
    else:
        # Cashiers see only their own held orders
        draft_orders = Order.objects.filter(
            status='HELD',
            created_by=request.user
        ).annotate(
            item_count_check=Count('items')
        ).filter(
            item_count_check__gt=0
        ).select_related(
            'customer', 'cashier_session'
        ).prefetch_related('items').order_by('-created_at')

    # Add computed fields for template
    draft_list = []
    for order in draft_orders:
        draft_list.append({
            'order': order,
            'total': order.total,
            'item_count': order.item_count,
        })

    context = {
        'draft_orders': draft_list,
        'is_manager': is_manager,
    }

    return render(request, 'orders/draft_orders_list.html', context)


@login_required
def draft_order_detail(request, pk):
    """
    View details of a held order
    """
    # Check if user is manager
    is_manager = request.user.groups.filter(name__in=['Admin', 'Manager']).exists()

    # Get the order
    if is_manager:
        order = get_object_or_404(Order, pk=pk, status='HELD')
    else:
        order = get_object_or_404(Order, pk=pk, status='HELD', created_by=request.user)

    # Check if order has items
    if order.items.count() == 0:
        messages.warning(request, "This order is empty")
        return redirect('orders:drafts_list')

    context = {
        'order': order,
        'items': order.items.all(),
        'is_manager': is_manager,
    }

    return render(request, 'orders/draft_order_detail.html', context)


@login_required
def draft_order_resume(request, pk):
    """
    Resume a held order - load it back into the cart
    """
    if request.method != 'POST':
        return redirect('orders:drafts_list')

    is_manager = request.user.groups.filter(name__in=['Admin', 'Manager']).exists()

    if is_manager:
        order = get_object_or_404(Order, pk=pk, status='HELD')
    else:
        order = get_object_or_404(Order, pk=pk, status='HELD', created_by=request.user)

    if order.items.count() == 0:
        messages.error(request, "Cannot resume an empty order")
        return redirect('orders:drafts_list')

    try:
        session = require_open_session(request.user)
    except ValidationError:
        messages.error(request, "No open cashier session. Start a session first.")
        return redirect('sales:start_session')

    existing_draft = Order.objects.filter(
        cashier_session=session,
        created_by=request.user,
        status='DRAFT'
    ).exclude(pk=order.pk).first()

    if existing_draft and existing_draft.items.count() > 0:
        messages.warning(
            request,
            "You have an active order in your cart. Please complete or hold it before resuming another order."
        )
        return redirect('orders:pos')

    # Change status from HELD to DRAFT
    order.status = 'DRAFT'
    order.cashier_session = session
    order.save(update_fields=['status', 'cashier_session', 'updated_at'])

    # ✅ Recalculate totals (same as other cart flows)
    OrderService._recalculate_totals(order)

    # ✅ Set as current order (critical for POS to load this cart)
    request.session['current_order_id'] = order.id
    request.session.modified = True

    messages.success(
        request,
        f"Order {order.order_number} has been resumed. Continue adding items or proceed to checkout."
    )
    return redirect('orders:pos')


@login_required
def draft_order_delete(request, pk):
    """
    Delete a held order
    """
    if request.method != 'POST':
        return redirect('orders:drafts_list')

    # Check if user is manager
    is_manager = request.user.groups.filter(name__in=['Admin', 'Manager']).exists()

    # Get the order
    if is_manager:
        order = get_object_or_404(Order, pk=pk, status='HELD')
    else:
        order = get_object_or_404(Order, pk=pk, status='HELD', created_by=request.user)

    order_number = order.order_number

    # Clear from session if it's the current order
    if request.session.get('current_order_id') == order.id:
        request.session.pop('current_order_id', None)

    order.delete()

    messages.success(
        request,
        f"Order {order_number} has been deleted."
    )

    return redirect('orders:drafts_list')


# ==================== HELPER FUNCTION ====================

def get_held_orders_count(user):
    """
    Get count of held orders for current user
    Used to show badge in POS
    """
    is_manager = user.groups.filter(name__in=['Admin', 'Manager']).exists()

    if is_manager:
        count = Order.objects.filter(
            status='HELD'  # ✅ HELD status
        ).annotate(
            item_count_check=Count('items')
        ).filter(item_count_check__gt=0).count()
    else:
        count = Order.objects.filter(
            status='HELD',  # ✅ FIXED: Was 'DRAFT', should be 'HELD'
            created_by=user
        ).annotate(
            item_count_check=Count('items')
        ).filter(item_count_check__gt=0).count()

    return count


# ===== ORDER MANAGEMENT =====

@login_required
def order_list(request):
    """
    List orders with daily sales breakdown for selected date
    """
    is_manager = request.user.is_superuser or request.user.groups.filter(
        name__in=['Admin', 'Manager']
    ).exists()

    # Exclude DRAFT and HELD
    if is_manager:
        orders = Order.objects.exclude(status__in=['DRAFT', 'HELD'])
    else:
        orders = Order.objects.filter(
            created_by=request.user
        ).exclude(status__in=['DRAFT', 'HELD'])

    orders = orders.select_related(
        'created_by', 'customer', 'cashier_session'
    ).prefetch_related('items')

    # Status filter
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)

    # Cashier filter (managers only)
    if is_manager:
        cashier_filter = request.GET.get('cashier')
        if cashier_filter:
            orders = orders.filter(created_by_id=cashier_filter)

    orders = orders.order_by('-created_at')

    # ===== DATE FILTER FOR DAILY BREAKDOWN =====
    today = datetime.now().date()

    # Get selected date from query param (default to today)
    selected_date_str = request.GET.get('date')
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = today
    else:
        selected_date = today

    # ===== DAILY BREAKDOWN FOR SELECTED DATE =====
    daily_sales = OrderItem.objects.filter(
        order__status='COMPLETED',
        order__created_at__date=selected_date  # ✅ Only selected date
    )

    if not is_manager:
        daily_sales = daily_sales.filter(order__created_by=request.user)
    elif is_manager and request.GET.get('cashier'):
        daily_sales = daily_sales.filter(order__created_by_id=request.GET.get('cashier'))

    daily_sales = daily_sales.values(
        'product_name',
        'variant_name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('line_total'),
        total_orders=Count('order', distinct=True)
    ).order_by('-total_quantity')

    # Convert to list for template
    daily_products = []
    total_items_sold = 0
    total_revenue = Decimal('0.00')

    for sale in daily_sales:
        daily_products.append({
            'product': sale['product_name'],
            'variant': sale['variant_name'],
            'quantity': sale['total_quantity'],
            'revenue': sale['total_revenue'],
            'orders': sale['total_orders'],
        })
        total_items_sold += sale['total_quantity']
        total_revenue += sale['total_revenue']

    # Get order count for selected date
    orders_on_date = Order.objects.filter(
        status='COMPLETED',
        created_at__date=selected_date
    )

    if not is_manager:
        orders_on_date = orders_on_date.filter(created_by=request.user)
    elif is_manager and request.GET.get('cashier'):
        orders_on_date = orders_on_date.filter(created_by_id=request.GET.get('cashier'))

    orders_count = orders_on_date.count()

    # Pagination
    paginator = Paginator(orders, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    cashiers = None
    if is_manager:
        cashiers = User.objects.filter(
            created_orders__isnull=False
        ).distinct().order_by('first_name', 'last_name', 'username')

    context = {
        'orders': page_obj,
        'page_obj': page_obj,
        'is_manager': is_manager,
        'cashiers': cashiers,

        # Daily breakdown data
        'selected_date': selected_date,
        'today': today,
        'daily_products': daily_products,
        'total_items_sold': total_items_sold,
        'total_revenue': total_revenue,
        'orders_count': orders_count,
    }

    return render(request, 'orders/order_list.html', context)


@login_required
@require_http_methods(["GET"])
def order_detail(request, pk):
    """
    View order details

    URL: GET /orders/<pk>/
    Returns: Order detail page
    """
    order = get_object_or_404(
        Order.objects.prefetch_related('items', 'order_payments'),
        pk=pk
    )

    items = order.items.select_related('variant', 'variant__product').all()
    payments = order.order_payments.all()

    context = {
        'order': order,
        'items': items,
        'payments': payments,
    }

    return render(request, 'orders/order_detail.html', context)


@login_required
@require_http_methods(["POST"])
def order_create(request):
    """
    Create new order manually

    URL: POST /orders/create/
    Returns: Redirect to order detail
    """
    try:
        from apps.sales.models import CashierSession
        session = CashierSession.objects.filter(
            cashier=request.user,
            closed_at__isnull=True
        ).first()

        order = OrderService.create_draft_order(user=request.user, session=session)

        messages.success(request, f'Order {order.order_number} created')
        return redirect('orders:order_detail', pk=order.id)

    except Exception as e:
        logger.exception(f"Error creating order: {e}")
        messages.error(request, f'Error: {str(e)}')
        return redirect('orders:order_list')


@login_required
@require_http_methods(["POST"])
def order_cancel(request, pk):
    """
    Cancel order

    URL: POST /orders/<pk>/cancel/
    Returns: Redirect to order detail
    """
    order = get_object_or_404(Order, pk=pk)

    try:
        reason = request.POST.get('reason', '').strip()
        OrderService.cancel_order(order, reason=reason, user=request.user)

        messages.success(request, f'Order {order.order_number} cancelled')
        return redirect('orders:order_detail', pk=order.id)

    except Exception as e:
        logger.exception(f"Error cancelling order: {e}")
        messages.error(request, f'Error: {str(e)}')
        return redirect('orders:order_detail', pk=order.id)



# ── helpers ──────────────────────────────────────────────────────────────────

def _render_cart(request, message=None, message_type='success'):
    """Render a fresh cart panel — shared by all customer cart views."""
    from apps.orders.models import Order, OrderItem
    from apps.customers.models import Customer

    order_id = request.session.get('current_order_id')
    order = None
    items = []

    if order_id:
        try:
            order = Order.objects.select_related('customer').get(
                pk=order_id,
                status='DRAFT',
                created_by=request.user
            )
            items = order.items.select_related('variant', 'variant__product').all()
        except Order.DoesNotExist:
            pass

    return render(request, 'orders/partials/cart_panel.html', {
        'order': order,
        'items': items,
        'message': message,
        'message_type': message_type,
    })


# ── Search customers for cart dropdown ───────────────────────────────────────

@login_required
@require_http_methods(["GET"])
def cart_customer_search(request):
    """
    HTMX endpoint — search customers for the cart panel dropdown.

    URL: GET /orders/cart/customer/search/?q=...
    Returns: customer_search_results.html partial
    """
    from apps.customers.models import Customer

    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        # Return nothing until user has typed at least 2 chars
        return render(request, 'orders/partials/customer_search_results.html', {
            'customers': [],
            'query': query,
        })

    customers = Customer.objects.filter(
        Q(full_name__icontains=query) |
        Q(phone__icontains=query) |
        Q(email__icontains=query) |
        Q(customer_number__icontains=query),
        is_active=True
    ).order_by('full_name')[:8]

    return render(request, 'orders/partials/customer_search_results.html', {
        'customers': customers,
        'query': query,
    })


# ── Set customer on current order ─────────────────────────────────────────────

@login_required
@require_http_methods(["POST"])
def cart_set_customer(request):
    """
    HTMX endpoint — link an existing customer to the current cart order.

    URL: POST /orders/cart/customer/set/
    Returns: updated cart_panel.html
    """
    from apps.customers.models import Customer
    from apps.orders.models import Order

    customer_id = request.POST.get('customer_id')

    if not customer_id:
        return _render_cart(request, 'No customer selected', 'error')

    try:
        customer = get_object_or_404(Customer, pk=customer_id, is_active=True)

        order_id = request.session.get('current_order_id')
        if not order_id:
            # No order yet — create one then assign customer
            order = Order.objects.create(
                created_by=request.user,
                status='DRAFT',
                customer=customer,
            )
            request.session['current_order_id'] = order.pk
            request.session.modified = True
        else:
            order = get_object_or_404(Order, pk=order_id, status='DRAFT', created_by=request.user)
            order.customer = customer
            order.save(update_fields=['customer'])

        logger.info(f"Customer '{customer.full_name}' linked to order {order.pk}")
        response = _render_cart(request, f'{customer.full_name} added to order', 'success')
        response["HX-Trigger"] = "customerSelected"
        return response

    except Exception as e:
        logger.exception(f"Error setting cart customer: {e}")
        return _render_cart(request, 'Could not add customer', 'error')


# ── Remove customer from current order ───────────────────────────────────────

@login_required
@require_http_methods(["POST"])
def cart_remove_customer(request):
    """
    HTMX endpoint — remove the linked customer from the current cart order.

    URL: POST /orders/cart/customer/remove/
    Returns: updated cart_panel.html
    """
    from apps.orders.models import Order

    order_id = request.session.get('current_order_id')
    if not order_id:
        return _render_cart(request)

    try:
        order = get_object_or_404(Order, pk=order_id, status='DRAFT', created_by=request.user)
        order.customer = None
        order.save(update_fields=['customer'])

        logger.info(f"Customer removed from order {order.pk}")
        return _render_cart(request, 'Customer removed', 'success')

    except Exception as e:
        logger.exception(f"Error removing cart customer: {e}")
        return _render_cart(request, 'Could not remove customer', 'error')


# ── Set walk-in (no customer) ─────────────────────────────────────────────────

@login_required
@require_http_methods(["POST"])
def cart_set_walkin(request):
    """
    HTMX endpoint — mark the order as walk-in (clears any customer).

    URL: POST /orders/cart/customer/walking/
    Returns: updated cart_panel.html
    """
    from apps.orders.models import Order

    order_id = request.session.get('current_order_id')
    if order_id:
        try:
            order = Order.objects.get(pk=order_id, status='DRAFT', created_by=request.user)
            if order.customer:
                order.customer = None
                order.save(update_fields=['customer'])
        except Order.DoesNotExist:
            pass

    return _render_cart(request, 'Continuing as walk-in', 'success')


# ── Quick-add customer form ───────────────────────────────────────────────────

@login_required
@require_http_methods(["GET"])
def cart_quick_add_customer_form(request):
    """
    HTMX endpoint — render the quick-add customer form inside the dropdown.

    URL: GET /orders/cart/customer/quick-add/
    Returns: customer_quick_add_form.html partial
    """
    prefill_name = request.GET.get('full_name', '')
    return render(request, 'orders/partials/customer_quick_add_form.html', {
        'prefill_name': prefill_name,
    })


# ── Quick-add customer (create + assign) ─────────────────────────────────────

@login_required
@require_http_methods(["POST"])
def cart_quick_add_customer(request):
    """
    HTMX endpoint — create a new customer and immediately link to cart order.

    URL: POST /orders/cart/customer/quick-add/
    Returns: updated cart_panel.html
    """
    from apps.customers.models import Customer
    from apps.orders.models import Order

    full_name  = request.POST.get('full_name', '').strip()
    phone = request.POST.get('phone', '').strip()
    email = request.POST.get('email', '').strip()

    if not full_name:
        return _render_cart(request, 'Customer name is required', 'error')

    try:
        # Create customer
        customer = Customer.objects.create(
            full_name=full_name,
            phone=phone or None,
            email=email or None,
            is_active=True,
        )

        # Link to current order
        order_id = request.session.get('current_order_id')
        if order_id:
            try:
                order = Order.objects.get(pk=order_id, status='DRAFT', created_by=request.user)
                order.customer = customer
                order.save(update_fields=['customer'])
            except Order.DoesNotExist:
                pass

        logger.info(f"Quick-added customer '{full_name}' and linked to cart")
        return _render_cart(request, f'{full_name} created and added to order', 'success')

    except Exception as e:
        logger.exception(f"Error quick-adding customer: {e}")
        return _render_cart(request, f'Could not create customer: {str(e)}', 'error')


@login_required
@require_POST
def mark_as_credit_sale(request):
    """
    Mark current order as credit sale by adding a CREDIT payment record
    """
    order_id = request.session.get('current_order_id')

    if not order_id:
        return JsonResponse({'error': 'No active order found in session'}, status=400)

    try:
        order = Order.objects.get(
            pk=order_id,
            status='DRAFT'
        )

        # Validate customer exists
        if not order.customer:
            return JsonResponse({
                'success': False,
                'error': 'Customer required for credit sales. Please link a customer first.'
            }, status=400)

        # Remove any existing CREDIT payments to avoid duplicates
        OrderPayment.objects.filter(
            order=order,
            payment_method='CREDIT'
        ).delete()

        # Create CREDIT payment marker (zero amount)
        OrderPayment.objects.create(
            order=order,
            amount=Decimal('0.00'),
            payment_method='CREDIT',
            notes=f'Credit sale for {order.customer.full_name}',
            processed_by=request.user,
            created_by=request.user
        )

        logger.info(f"Order {order.order_number} marked as credit sale for customer {order.customer.full_name}")

        return JsonResponse({
            'success': True,
            'message': f'Order marked as credit sale for {order.customer.full_name}',
            'customer_name': order.customer.full_name
        })

    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found or not in DRAFT status")
        return JsonResponse({
            'success': False,
            'error': 'Order not found or already completed'
        }, status=404)
    except Exception as e:
        logger.error(f"Error marking credit sale: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Error: {str(e)}'
        }, status=500)
