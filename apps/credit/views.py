# apps/credit/views.py
"""
Credit Ledger Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models
from .models import CreditLedger, CreditPayment
from .services import CreditLedgerService
from apps.customers.models import Customer
from apps.orders.models import Order


@login_required
def customer_credit_dashboard(request, customer_id):
    """
    Customer credit dashboard showing outstanding balances and history
    """
    customer = get_object_or_404(Customer, pk=customer_id)

    # Get credit summary
    summary = customer.get_credit_summary()

    # Get recent transactions
    recent_entries = customer.credit_ledger_entries.select_related(
        'order', 'created_by'
    ).prefetch_related('payments')[:20]

    context = {
        'customer': customer,
        'summary': summary,
        'recent_entries': recent_entries,
    }

    return render(request, 'credit/customer_dashboard.html', context)


@login_required
def record_credit_payment(request, ledger_id):
    """
    Record payment against a credit ledger entry
    """
    ledger = get_object_or_404(CreditLedger, ledger_id=ledger_id)

    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount'))
            payment_method = request.POST.get('payment_method')
            reference = request.POST.get('reference', '')
            notes = request.POST.get('notes', '')

            # Get cashier session if available
            cashier_session = getattr(request.user, 'active_session', None)

            # Record payment
            payment = CreditLedgerService.record_payment(
                ledger=ledger,
                amount=amount,
                payment_method=payment_method,
                user=request.user,
                reference=reference,
                notes=notes,
                cashier_session=cashier_session
            )

            messages.success(
                request,
                f"✅ Payment of ₦{amount:,.2f} recorded successfully. "
                f"Remaining balance: ₦{ledger.balance_outstanding:,.2f}"
            )

            return redirect('credit:ledger_detail', ledger_id=ledger_id)

        except Exception as e:
            messages.error(request, f"❌ Error: {str(e)}")

    context = {
        'ledger': ledger,
        'payment_methods': CreditPayment.PAYMENT_METHODS,
    }

    return render(request, 'credit/record_payment.html', context)


@login_required
def ledger_detail(request, ledger_id):
    """
    Detailed view of a credit ledger entry
    """
    ledger = get_object_or_404(
        CreditLedger.objects.select_related(
            'customer', 'order', 'created_by'
        ).prefetch_related('payments'),
        ledger_id=ledger_id
    )

    context = {
        'ledger': ledger,
        'payments': ledger.payments.all(),
    }

    return render(request, 'credit/ledger_detail.html', context)


@login_required
def customer_statement(request, customer_id):
    """
    Generate customer statement of account
    """
    customer = get_object_or_404(Customer, pk=customer_id)

    # Get date range from request
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        # Default to last 90 days
        start_date = timezone.now().date() - timedelta(days=90)

    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        end_date = timezone.now().date()

    # Generate statement
    statement = CreditLedgerService.get_customer_statement(
        customer=customer,
        start_date=start_date,
        end_date=end_date
    )

    context = {
        'customer': customer,
        'statement': statement,
    }

    return render(request, 'credit/customer_statement.html', context)


@login_required
def aging_report(request):
    """
    Accounts receivable aging report
    """

    aging = CreditLedgerService.get_aging_report()
    overdue_customers = CreditLedgerService.get_overdue_customers()

    total = aging.get("total", 0)

    if total:
        aging["current_percent"] = (aging["current"] / total) * 100
        aging["days_31_60_percent"] = (aging["days_31_60"] / total) * 100
        aging["days_61_90_percent"] = (aging["days_61_90"] / total) * 100
        aging["over_90_percent"] = (aging["over_90"] / total) * 100
    else:
        aging["current_percent"] = 0
        aging["days_31_60_percent"] = 0
        aging["days_61_90_percent"] = 0
        aging["over_90_percent"] = 0

    context = {
        'aging': aging,
        'overdue_customers': overdue_customers,
        'report_date': timezone.now().date(),
    }

    return render(request, 'credit/aging_report.html', context)


@login_required
def outstanding_balance_report(request):
    """
    Report of all customers with outstanding balances
    """
    from django.db.models import Sum, Count, Min

    customers_with_debt = Customer.objects.filter(
        credit_ledger_entries__balance_outstanding__gt=0,
        credit_ledger_entries__status__in=['PENDING', 'PARTIAL', 'OVERDUE']
    ).distinct().annotate(
        total_outstanding=Sum('credit_ledger_entries__balance_outstanding'),
        oldest_debt_date=Min('credit_ledger_entries__transaction_date'),
        number_of_unpaid=Count('credit_ledger_entries', filter=models.Q(
            credit_ledger_entries__balance_outstanding__gt=0
        ))
    ).order_by('-total_outstanding')

    # Calculate totals
    grand_total = customers_with_debt.aggregate(
        total=Sum('total_outstanding')
    )['total'] or Decimal('0.00')

    context = {
        'customers': customers_with_debt,
        'grand_total': grand_total,
        'total_customers': customers_with_debt.count(),
    }

    return render(request, 'credit/outstanding_balance_report.html', context)


@login_required
def collection_report(request):

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = timezone.now().date() - timedelta(days=30)

    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        end_date = timezone.now().date()

    summary = CreditLedgerService.get_collection_summary(
        start_date=start_date,
        end_date=end_date
    )

    # ✅ Calculate average payment
    if summary["payment_count"] > 0:
        summary["average_payment"] = summary["total_collected"] / summary["payment_count"]
    else:
        summary["average_payment"] = 0

    # ✅ Calculate daily averages
    for day in summary["by_day"]:
        if day["count"] > 0:
            day["avg_payment"] = day["total"] / day["count"]
        else:
            day["avg_payment"] = 0

    context = {
        "summary": summary,
        "start_date": start_date,
        "end_date": end_date,
    }

    return render(request, "credit/collection_report.html", context)


@login_required
def credit_ledger_list(request):
    """
    List all credit ledger entries with filters
    """
    entries = CreditLedger.objects.select_related(
        'customer', 'order', 'created_by'
    ).all()

    # Apply filters
    status = request.GET.get('status')
    if status:
        entries = entries.filter(status=status)

    customer_id = request.GET.get('customer')
    if customer_id:
        entries = entries.filter(customer_id=customer_id)

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(entries, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'status_choices': CreditLedger.STATUS_CHOICES,
    }

    return render(request, 'credit/ledger_list.html', context)


@login_required
def credit_customers_list(request):
    """
    List all customers with credit accounts
    """
    from django.db.models import Sum, Count, Q

    customers = Customer.objects.filter(
        credit_limit__gt=0
    ).annotate(
        total_outstanding=Sum(
            'credit_ledger_entries__balance_outstanding',
            filter=Q(credit_ledger_entries__status__in=['PENDING', 'PARTIAL', 'OVERDUE'])
        ),
        credit_count=Count('credit_ledger_entries')
    )

    for c in customers:
        outstanding = c.total_outstanding or 0
        limit = c.credit_limit or 1
        c.utilization = (outstanding / limit) * 100 if limit else 0

    context = {
        'customers': customers,
    }

    return render(request, 'credit/customers_list.html', context)