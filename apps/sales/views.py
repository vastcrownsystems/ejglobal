# apps/sales/views.py - FIXED VERSION

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum, Count
from .models import CashierSession, Register, Store
from .forms import StartSessionForm, CloseSessionForm, StoreForm, RegisterForm
from decimal import Decimal
from apps.core.decorators import group_required


# ==================== STORE MANAGEMENT ====================

@group_required("Admin", "Manager")
def store_list(request):
    """List all stores"""
    stores = Store.objects.annotate(
        register_count=Count('registers'),
        active_register_count=Count('registers', filter=Q(registers__is_active=True))
    ).order_by('name')

    context = {
        'stores': stores,
        'title': 'Store Management'
    }
    return render(request, 'sales/stores/list.html', context)


@group_required("Admin", "Manager")
def store_create(request):
    """Create new store"""
    if request.method == 'POST':
        form = StoreForm(request.POST)
        if form.is_valid():
            store = form.save()
            messages.success(request, f'Store "{store.name}" created successfully!')
            return redirect('sales:store_list')
    else:
        form = StoreForm()

    context = {
        'form': form,
        'title': 'Create Store'
    }
    return render(request, 'sales/stores/form.html', context)


@group_required("Admin", "Manager")
def store_edit(request, pk):
    """Edit existing store"""
    store = get_object_or_404(Store, pk=pk)

    if request.method == 'POST':
        form = StoreForm(request.POST, instance=store)
        if form.is_valid():
            store = form.save()
            messages.success(request, f'Store "{store.name}" updated successfully!')
            return redirect('sales:store_list')
    else:
        form = StoreForm(instance=store)

    context = {
        'form': form,
        'store': store,
        'title': f'Edit Store: {store.name}'
    }
    return render(request, 'sales/stores/form.html', context)


@group_required("Admin", "Manager")
def store_detail(request, pk):
    """View store details with registers"""
    store = get_object_or_404(Store, pk=pk)

    registers = Register.objects.filter(store=store).annotate(
        session_count=Count('sessions')
    ).order_by('name')

    # Get active sessions for this store
    active_sessions = CashierSession.objects.filter(
        store=store,
        closed_at__isnull=True
    ).select_related('register', 'cashier')

    # Check which registers have active sessions
    active_register_ids = active_sessions.values_list('register_id', flat=True)

    context = {
        'store': store,
        'registers': registers,
        'active_sessions': active_sessions,
        'active_register_ids': list(active_register_ids),
        'title': store.name
    }
    return render(request, 'sales/stores/detail.html', context)


# ==================== REGISTER MANAGEMENT ====================

@group_required("Admin", "Manager")
def register_list(request):
    """List all registers"""
    registers = Register.objects.select_related('store').annotate(
        session_count=Count('sessions')
    ).order_by('store__name', 'name')

    # Check which registers have active sessions
    active_register_ids = CashierSession.objects.filter(
        closed_at__isnull=True
    ).values_list('register_id', flat=True)

    context = {
        'registers': registers,
        'active_register_ids': list(active_register_ids),
        'title': 'Register Management'
    }
    return render(request, 'sales/registers/list.html', context)


@group_required("Admin", "Manager")
def register_create(request):
    """Create new register"""
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            register = form.save()
            messages.success(request, f'Register "{register.name}" created successfully!')
            return redirect('sales:register_list')
    else:
        form = RegisterForm()

    context = {
        'form': form,
        'title': 'Create Register'
    }
    return render(request, 'sales/registers/form.html', context)


@group_required("Admin", "Manager")
def register_edit(request, pk):
    """Edit existing register"""
    register = get_object_or_404(Register, pk=pk)

    if request.method == 'POST':
        form = RegisterForm(request.POST, instance=register)
        if form.is_valid():
            register = form.save()
            messages.success(request, f'Register "{register.name}" updated successfully!')
            return redirect('sales:register_list')
    else:
        form = RegisterForm(instance=register)

    context = {
        'form': form,
        'register': register,
        'title': f'Edit Register: {register.name}'
    }
    return render(request, 'sales/registers/form.html', context)


@group_required("Admin", "Manager")
def register_detail(request, pk):
    """View register details with session history"""
    register = get_object_or_404(Register, pk=pk)

    # Get session history
    sessions = CashierSession.objects.filter(
        register=register
    ).select_related('cashier').order_by('-opened_at')[:20]

    # Current session
    current_session = sessions.filter(closed_at__isnull=True).first()

    # Stats
    total_sessions = CashierSession.objects.filter(register=register).count()
    closed_sessions = CashierSession.objects.filter(
        register=register,
        closed_at__isnull=False
    )

    total_cash_handled = closed_sessions.aggregate(
        total=Sum('closing_cash')
    )['total'] or Decimal('0.00')

    context = {
        'register': register,
        'sessions': sessions,
        'current_session': current_session,
        'total_sessions': total_sessions,
        'total_cash_handled': total_cash_handled,
        'title': register.name
    }
    return render(request, 'sales/registers/detail.html', context)


# ==================== SESSION MANAGEMENT ====================

@login_required
def session_dashboard(request):
    """Dashboard showing current session status"""
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    from apps.orders.models import Order, OrderPayment  # ✅ FIXED: Import OrderPayment from orders app

    user = request.user

    # Check if user is manager/admin
    is_manager = user.is_superuser or user.groups.filter(name__in=['Admin', 'Manager']).exists()

    # Get user's current open session
    current_session = CashierSession.objects.filter(
        cashier=user,
        closed_at__isnull=True
    ).select_related('register', 'store').first()

    # Get recent closed sessions based on role
    if is_manager:
        # Managers see all recent closed sessions
        sessions_queryset = CashierSession.objects.filter(
            closed_at__isnull=False
        ).select_related('register', 'store', 'cashier').order_by('-closed_at')
    else:
        # Regular users see only their own recent closed sessions
        sessions_queryset = CashierSession.objects.filter(
            cashier=user,
            closed_at__isnull=False
        ).select_related('register', 'store', 'cashier').order_by('-closed_at')

    # Calculate total sales for each session
    sessions_with_sales = []
    for session in sessions_queryset[:50]:  # Limit to last 50 for performance
        # Get all orders for this session
        session_orders = Order.objects.filter(
            cashier_session=session,
            status__in=['CONFIRMED', 'COMPLETED']
        )

        # Get all payments for these orders using the correct relationship
        # OrderPayment has foreign key to Order with related_name='order_payments'
        payments = OrderPayment.objects.filter(
            order__in=session_orders
        )

        # Calculate sales by payment method
        cash_sales = payments.filter(payment_method='CASH').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        card_sales = payments.filter(payment_method='CARD').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        transfer_sales = payments.filter(payment_method='TRANSFER').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        total_sales = cash_sales + card_sales + transfer_sales

        # Add sales data to session object
        session.total_sales = total_sales
        session.cash_sales = cash_sales
        session.card_sales = card_sales
        session.transfer_sales = transfer_sales

        sessions_with_sales.append(session)

    # Implement pagination
    paginator = Paginator(sessions_with_sales, 10)  # 10 sessions per page
    page = request.GET.get('page', 1)

    try:
        recent_sessions = paginator.page(page)
    except PageNotAnInteger:
        recent_sessions = paginator.page(1)
    except EmptyPage:
        recent_sessions = paginator.page(paginator.num_pages)

    context = {
        'current_session': current_session,
        'recent_sessions': recent_sessions,
        'is_manager': is_manager,
    }

    return render(request, 'sales/session_dashboard.html', context)


@login_required
def start_session(request):
    """Start a new cashier session"""

    # ✅ If cashier already has open session, go dashboard (not forced close)
    existing_session = CashierSession.objects.filter(
        cashier=request.user,
        closed_at__isnull=True
    ).first()
    if existing_session:
        messages.info(request, "You already have an active session.")
        return redirect('sales:session_dashboard')

    open_register_ids = CashierSession.objects.filter(
        closed_at__isnull=True
    ).values_list('register_id', flat=True)

    available_qs = Register.objects.filter(
        is_active=True
    ).exclude(
        id__in=open_register_ids
    ).select_related('store')

    available_registers = available_qs.count()

    if request.method == 'POST':
        form = StartSessionForm(request.POST, user=request.user, available_registers_qs=available_qs)
        if form.is_valid():
            session = form.save()
            messages.success(request, f'Session started successfully at {session.register.name}!')
            return redirect('sales:session_dashboard')
    else:
        form = StartSessionForm(user=request.user, available_registers_qs=available_qs)

    return render(request, 'sales/start_session.html', {
        'form': form,
        'available_registers': available_registers,
    })


@login_required
def close_session(request, session_id):
    """Close cashier session with sales calculation"""
    session = get_object_or_404(
        CashierSession,
        id=session_id,
        cashier=request.user,
        closed_at__isnull=True
    )

    # ✅ FIXED: Import OrderPayment from correct location
    from apps.orders.models import Order, OrderPayment

    # Get all orders for this session
    session_orders = Order.objects.filter(
        cashier_session=session,
        status__in=['CONFIRMED', 'COMPLETED']
    )

    # Count orders
    order_count = session_orders.count()

    # Get all payments for orders in this session
    # OrderPayment has foreign key to Order with related_name='order_payments'
    payments = OrderPayment.objects.filter(
        order__in=session_orders
    )

    # Sum by payment method (note: payment_method field, not method)
    cash_sales = payments.filter(payment_method='CASH').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    card_sales = payments.filter(payment_method='CARD').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    transfer_sales = payments.filter(payment_method='TRANSFER').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    # Calculate totals
    total_sales = cash_sales + card_sales + transfer_sales
    expected_cash = session.opening_cash + cash_sales

    if request.method == "POST":
        closing_cash = request.POST.get("closing_cash")

        try:
            closing_cash = Decimal(closing_cash)
            if closing_cash < 0:
                raise ValueError("Closing cash cannot be negative")
        except ValueError as e:
            messages.error(request, f"Invalid closing cash: {e}")
            return redirect("sales:close_session", session_id=session.id)

        # Save session
        session.closing_cash = closing_cash
        session.closed_at = timezone.now()
        session.save()

        # Calculate variance
        variance = closing_cash - expected_cash

        # Show appropriate message based on variance
        if variance == 0:
            messages.success(request, f"✅ Session closed perfectly! No variance.")
        elif variance > 0:
            messages.warning(request, f"⚠️ Session closed with +₦{variance:.2f} overage")
        else:
            messages.error(request, f"❌ Session closed with ₦{abs(variance):.2f} shortage")

        return redirect("sales:session_dashboard")

    context = {
        "session": session,
        "order_count": order_count,
        "cash_sales": cash_sales,
        "card_sales": card_sales,
        "transfer_sales": transfer_sales,
        "total_sales": total_sales,
        "expected_cash": expected_cash,
    }

    return render(request, "sales/close_session.html", context)


@login_required
def session_detail(request, session_id):
    """View details of a specific session"""
    session = get_object_or_404(
        CashierSession,
        id=session_id,
        cashier=request.user
    )

    # Calculate duration
    if session.closed_at:
        duration = session.closed_at - session.opened_at
    else:
        duration = timezone.now() - session.opened_at

    hours = int(duration.total_seconds() // 3600)
    minutes = int((duration.total_seconds() % 3600) // 60)

    # Get session orders
    from apps.orders.models import Order, OrderPayment
    session_orders = Order.objects.filter(
        cashier_session=session
    ).select_related('customer')

    # Calculate totals
    payments = OrderPayment.objects.filter(
        order__in=session_orders
    )

    total_sales = payments.aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    cash_sales = payments.filter(payment_method='CASH').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    # Calculate cash difference
    cash_difference = None
    if session.closing_cash is not None:
        expected_cash = session.opening_cash + cash_sales
        cash_difference = session.closing_cash - expected_cash

    context = {
        'session': session,
        'duration_hours': hours,
        'duration_minutes': minutes,
        'session_orders': session_orders,
        'total_sales': total_sales,
        'cash_sales': cash_sales,
        'order_count': session_orders.count(),
        'cash_difference': cash_difference,
    }

    return render(request, 'sales/session_detail.html', context)


# Helper function
def _format_duration(session):
    """Format session duration as human-readable string"""
    if not session.closed_at:
        return 'Ongoing'

    duration = session.closed_at - session.opened_at
    hours = int(duration.total_seconds() // 3600)
    minutes = int((duration.total_seconds() % 3600) // 60)

    if hours > 0:
        return f'{hours} hour{"s" if hours != 1 else ""}, {minutes} minute{"s" if minutes != 1 else ""}'
    else:
        return f'{minutes} minute{"s" if minutes != 1 else ""}'