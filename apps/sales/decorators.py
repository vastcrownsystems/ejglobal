# apps/sales/decorators.py
"""
Decorators for cashier session access control
Place this file in: apps/sales/decorators.py
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from .models import CashierSession  # Import from sales app


def session_required(view_func):
    """
    Decorator to require an active cashier session before accessing a view.

    Usage:
        @login_required
        @session_required
        def pos_interface(request):
            # This view requires both login AND active session
            ...

    Redirects to session dashboard if no active session exists.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Check if user has an active session
        try:
            active_session = CashierSession.objects.get(
                cashier=request.user,
                status='open'
            )
            # Store session in request for easy access
            request.active_session = active_session
            return view_func(request, *args, **kwargs)
        except CashierSession.DoesNotExist:
            messages.warning(
                request,
                "⚠️ You must start a cashier session before accessing the POS."
            )
            return redirect('sales:session_dashboard')  # ← Uses 'sales' namespace
        except CashierSession.MultipleObjectsReturned:
            messages.error(
                request,
                "❌ Multiple open sessions detected. Please contact administrator."
            )
            return redirect('sales:session_dashboard')

    return wrapper


def session_forbidden(view_func):
    """
    Decorator to forbid access if user already has an active session.

    Usage:
        @login_required
        @session_forbidden
        def start_session(request):
            # This view should only be accessible if NO active session
            ...

    Useful for session start view - prevents starting multiple sessions.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            active_session = CashierSession.objects.get(
                cashier=request.user,
                status='open'
            )
            messages.info(
                request,
                f"ℹ️ You already have an active session (started {active_session.started_at.strftime('%I:%M %p')})"
            )
            return redirect('pos:pos_interface')
        except CashierSession.DoesNotExist:
            return view_func(request, *args, **kwargs)

    return wrapper


def session_owner_required(view_func):
    """
    Decorator to require that the user is the owner of the session.

    Usage:
        @login_required
        @session_owner_required
        def close_session(request, session_id):
            # User must own this session
            ...

    Looks for 'session_id' in URL kwargs.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Get session ID from URL kwargs
        session_id = kwargs.get('session_id')

        if not session_id:
            messages.error(request, "❌ No session specified.")
            return redirect('sales:session_dashboard')

        try:
            session = CashierSession.objects.get(pk=session_id)

            # Check if user owns this session
            if session.cashier != request.user:
                messages.error(
                    request,
                    "❌ You can only manage your own sessions."
                )
                return redirect('sales:session_dashboard')

            # Store session in request
            request.session_obj = session
            return view_func(request, *args, **kwargs)

        except CashierSession.DoesNotExist:
            messages.error(request, "❌ Session not found.")
            return redirect('sales:session_dashboard')

    return wrapper