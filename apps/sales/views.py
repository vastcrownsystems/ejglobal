# apps/sales/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from .models import CashierSession, Register
from .forms import StartSessionForm, CloseSessionForm
from decimal import Decimal


@login_required
def session_dashboard(request):
    """Dashboard showing current session status"""
    # Get user's current open session
    current_session = CashierSession.objects.filter(
        cashier=request.user,
        closed_at__isnull=True
    ).select_related('register', 'store').first()

    # Get recent closed sessions
    recent_sessions = CashierSession.objects.filter(
        cashier=request.user,
        closed_at__isnull=False
    ).select_related('register', 'store').order_by('-closed_at')[:5]

    context = {
        'current_session': current_session,
        'recent_sessions': recent_sessions,
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
    session = get_object_or_404(
        CashierSession,
        id=session_id,
        cashier=request.user,
        closed_at__isnull=True
    )

    if request.method == "POST":
        closing_cash = request.POST.get("closing_cash")

        try:
            closing_cash = Decimal(closing_cash)
            if closing_cash < 0:
                raise ValueError
        except Exception:
            messages.error(request, "Enter a valid closing cash amount.")
            return redirect("sales:close_session", session_id=session.id)

        session.closing_cash = closing_cash
        session.closed_at = timezone.now()
        session.save()

        messages.success(
            request,
            f"Session closed. Variance: ₦{session.variance:.2f}"
        )
        return redirect("sales:session_dashboard")

    return render(request, "sales/close_session.html", {
        "session": session,
        "expected_cash": session.expected_cash,
    })


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

    # Calculate cash difference
    cash_difference = None
    if session.closing_cash is not None:
        cash_difference = session.closing_cash - session.opening_cash

    context = {
        'session': session,
        'duration_hours': hours,
        'duration_minutes': minutes,
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