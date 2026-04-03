# apps/customers/views.py - Complete Customer Views with Credit Management

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Sum, Count, Avg, F
from django.contrib import messages
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from datetime import timedelta
from decimal import Decimal
import json

from .models import Customer, SalesPerson
from .services import CustomerService, SalesPersonService


def user_can_manage_credit(user):
    """
    Check if user has permission to manage customer credit

    Returns True if user is:
    - Superuser (admin)
    - Staff member
    - Member of 'Manager' or 'Admin' group
    """
    if user.is_superuser or user.is_staff:
        return True

    # Check if user is in Manager or Admin group
    return user.groups.filter(name__in=['Manager', 'Admin']).exists()


@login_required
@require_http_methods(["GET"])
def customer_dashboard(request):
    """
    Customer management dashboard with analytics

    URL: GET /customers/dashboard/
    """
    # Total customers
    total_customers = Customer.objects.filter(is_active=True).count()

    # New customers this month
    this_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_this_month = Customer.objects.filter(
        is_active=True,
        created_at__gte=this_month_start
    ).count()

    # Total revenue
    customer_stats = Customer.objects.filter(is_active=True).aggregate(
        total_revenue=Sum('total_spent'),
        avg_value=Avg('total_spent'),
        total_orders=Sum('total_orders')
    )

    # Active customers (purchased in last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    active_customers = Customer.objects.filter(
        is_active=True,
        last_purchase_date__gte=thirty_days_ago
    ).count()

    # Top customers
    top_customers = Customer.objects.filter(
        is_active=True,
        total_spent__gt=0
    ).order_by('-total_spent')[:10]

    # Recent customers
    recent_customers = Customer.objects.filter(
        is_active=True
    ).order_by('-created_at')[:10]

    # Credit statistics (for managers/admins only)
    credit_stats = None
    if user_can_manage_credit(request.user):
        from apps.credit.models import CreditLedger
        from django.db.models import DecimalField
        from django.db.models.functions import Coalesce

        total_outstanding = CreditLedger.objects.filter(
            customer__is_active=True,
            status__in=['PENDING', 'PARTIAL', 'OVERDUE']
        ).aggregate(total=Sum('balance_outstanding'))['total'] or Decimal('0.00')

        credit_stats = {
            'total_credit_extended': Customer.objects.filter(
                is_active=True,
                credit_limit__gt=0
            ).aggregate(total=Sum('credit_limit'))['total'] or Decimal('0.00'),
            'total_outstanding': total_outstanding,
            'customers_with_credit': Customer.objects.filter(
                is_active=True,
                credit_limit__gt=0
            ).count(),
            'overdue_customers': Customer.objects.filter(
                is_active=True,
                credit_status='SUSPENDED'
            ).count()
        }

    # Average orders per customer
    avg_orders = customer_stats['total_orders'] / total_customers if total_customers > 0 else 0

    context = {
        'total_customers': total_customers,
        'new_this_month': new_this_month,
        'total_revenue': customer_stats['total_revenue'] or 0,
        'avg_customer_value': customer_stats['avg_value'] or 0,
        'active_customers': active_customers,
        'total_orders': customer_stats['total_orders'] or 0,
        'avg_orders_per_customer': avg_orders,
        'top_customers': top_customers,
        'recent_customers': recent_customers,
        'credit_stats': credit_stats,
        'can_manage_credit': user_can_manage_credit(request.user),
    }

    return render(request, 'customers/customer_dashboard.html', context)


@login_required
@require_http_methods(["GET"])
def customer_search_modal(request):
    """
    Load customer search/add modal (for POS)

    URL: GET /customers/modal/
    """
    return render(request, 'customers/customer_search_modal.html')


@login_required
@require_http_methods(["GET"])
def customer_search(request):
    """
    HTMX endpoint for searching customers

    URL: GET /customers/search/?q=query
    """
    query = request.GET.get('q', '').strip()

    if not query or len(query) < 2:
        return render(request, 'customers/partials/search_results.html', {
            'customers': [],
            'message': 'Enter at least 2 characters to search'
        })

    # Search customers
    customers = CustomerService.search_customers(query, limit=10)

    return render(request, 'customers/partials/search_results.html', {
        'customers': customers,
        'query': query
    })


@login_required
@require_http_methods(["POST"])
def quick_add_customer(request):
    """
    Quick add customer and associate with current order

    URL: POST /customers/quick-add/
    """
    try:
        # Create customer
        customer = CustomerService.quick_add(
            full_name=request.POST.get('full_name'),
            phone=request.POST.get('phone', ''),
            email=request.POST.get('email', ''),
            customer_type=request.POST.get('customer_type', 'INDIVIDUAL'),
            created_by=request.user
        )

        # Associate with current order
        order_id = request.session.get('current_order_id')
        if order_id:
            from apps.orders.models import Order
            try:
                order = Order.objects.get(pk=order_id, status='DRAFT')
                order.associate_customer(customer)
            except Order.DoesNotExist:
                pass

        # Close modal and refresh
        return HttpResponse(
            '<script>'
            'closeCustomerModal(); '
            'htmx.ajax("GET", "/pos/cart/", {target: "#cartPanel", swap: "outerHTML"});'
            '</script>'
        )

    except Exception as e:
        return HttpResponse(
            f'<div class="alert alert-error">Error: {str(e)}</div>'
        )


@login_required
@require_http_methods(["POST"])
def select_customer(request):
    """
    Select existing customer for current order

    URL: POST /customers/select/
    """
    try:
        data = json.loads(request.body)
        customer_id = data.get('customer_id')

        # Get customer
        customer = get_object_or_404(Customer, pk=customer_id, is_active=True)

        # Associate with current order
        order_id = request.session.get('current_order_id')
        if order_id:
            from apps.orders.models import Order
            order = Order.objects.get(pk=order_id, status='DRAFT')
            order.associate_customer(customer)

            return JsonResponse({
                'success': True,
                'customer_name': customer.full_name,
                'message': f'Customer {customer.full_name} added to order'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'No active order'
            })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_http_methods(["POST"])
def skip_customer(request):
    """
    Skip customer (walk-in sale)

    URL: POST /customers/skip/
    """
    # Get optional walk-in reference name
    walk_in_name = request.POST.get('walk_in_name', '').strip()

    # Update order with walk-in name (if provided)
    order_id = request.session.get('current_order_id')
    if order_id and walk_in_name:
        from apps.orders.models import Order
        try:
            order = Order.objects.get(pk=order_id, status='DRAFT')
            order.customer_name = walk_in_name
            order.save(update_fields=['customer_name'])
        except Order.DoesNotExist:
            pass

    # Close modal
    return HttpResponse(
        '<script>closeCustomerModal();</script>'
    )


@login_required
@require_http_methods(["GET"])
def customer_list(request):
    """
    List all customers with filters

    URL: GET /customers/
    """
    customers = Customer.objects.filter(is_active=True)

    # Apply search
    search = request.GET.get('search')
    if search:
        customers = customers.filter(
            Q(full_name__icontains=search) |
            Q(customer_number__icontains=search) |
            Q(phone__icontains=search) |
            Q(email__icontains=search)
        )

    customer_type = request.GET.get('type')
    if customer_type:
        customers = customers.filter(customer_type=customer_type)

    # Apply sorting
    sort = request.GET.get('sort', '-created_at')
    customers = customers.order_by(sort)

    # Calculate stats
    total_customers = customers.count()

    # Active customers (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    active_count = customers.filter(last_purchase_date__gte=thirty_days_ago).count()

    # Total value
    total_value = customers.aggregate(total=Sum('total_spent'))['total'] or 0

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(customers, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'customers': page_obj.object_list,
        'active_customers_count': active_count,
        'total_value': total_value,
        'can_manage_credit': user_can_manage_credit(request.user),
    }

    return render(request, 'customers/customer_list.html', context)


@login_required
@require_http_methods(["GET"])
def customer_detail(request, pk):
    """
    Customer detail page with order history

    URL: GET /customers/<pk>/
    """
    customer = get_object_or_404(
        Customer.objects.prefetch_related('orders'),
        pk=pk
    )

    # Get order history
    orders = customer.get_orders()[:20]

    # Get credit summary if user has permission
    credit_summary = None
    if user_can_manage_credit(request.user):
        credit_summary = customer.get_credit_summary()

    context = {
        'customer': customer,
        'orders': orders,
        'credit_summary': credit_summary,
        'can_manage_credit': user_can_manage_credit(request.user),
    }

    return render(request, 'customers/customer_detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def customer_create(request):
    """
    Create new customer (full form)

    URL: GET/POST /customers/create/
    """
    if request.method == 'POST':
        try:
            # Create customer with basic info
            customer = CustomerService.create_customer(
                full_name=request.POST.get('full_name'),
                phone=request.POST.get('phone', ''),
                email=request.POST.get('email', ''),
                customer_type=request.POST.get('customer_type', 'INDIVIDUAL'),
                address_line=request.POST.get('address_line', ''),
                city=request.POST.get('city', ''),
                state=request.POST.get('state', ''),
                sales_person_id=request.POST.get('sales_person_id') or None,
                created_by=request.user
            )

            # Handle credit fields (admin/manager only)
            if user_can_manage_credit(request.user):
                credit_limit = request.POST.get('credit_limit', '0')
                credit_terms_days = request.POST.get('credit_terms_days', '30')
                credit_status = request.POST.get('credit_status', 'APPROVED')

                try:
                    customer.credit_limit = Decimal(credit_limit) if credit_limit else Decimal('0.00')
                    customer.credit_terms_days = int(credit_terms_days) if credit_terms_days else 30
                    customer.credit_status = credit_status
                    customer.save(update_fields=['credit_limit', 'credit_terms_days', 'credit_status'])
                except (ValueError, TypeError):
                    messages.warning(request, '⚠️ Invalid credit values provided, using defaults')

            messages.success(
                request,
                f'✅ Customer {customer.full_name} created successfully'
            )
            return redirect('customers:customer_detail', pk=customer.pk)

        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    context = {
        'can_manage_credit': user_can_manage_credit(request.user),
        'sales_persons': SalesPerson.objects.filter(is_active=True).order_by('full_name'),
    }

    return render(request, 'customers/customer_form.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def customer_edit(request, pk):
    """
    Edit customer

    URL: GET/POST /customers/<pk>/edit/
    """
    customer = get_object_or_404(Customer, pk=pk)

    if request.method == 'POST':
        try:
            # Update basic fields
            customer.full_name = request.POST.get('full_name')
            customer.phone = request.POST.get('phone', '')
            customer.email = request.POST.get('email', '')
            customer.customer_type = request.POST.get('customer_type')
            customer.address_line = request.POST.get('address_line', '')
            customer.city = request.POST.get('city', '')
            customer.state = request.POST.get('state', '')

            # Update sales person assignment
            sp_id = request.POST.get('sales_person_id') or None
            if sp_id:
                try:
                    customer.sales_person = SalesPerson.objects.get(pk=sp_id, is_active=True)
                except SalesPerson.DoesNotExist:
                    pass
            else:
                customer.sales_person = None

            # Handle credit fields (admin/manager only)
            if user_can_manage_credit(request.user):
                credit_limit = request.POST.get('credit_limit', '0')
                credit_terms_days = request.POST.get('credit_terms_days', '30')
                credit_status = request.POST.get('credit_status', 'APPROVED')

                try:
                    new_credit_limit = Decimal(credit_limit) if credit_limit else Decimal('0.00')

                    # Warn if reducing credit limit below outstanding balance
                    if new_credit_limit < customer.total_credit_outstanding:
                        messages.warning(
                            request,
                            f'⚠️ Credit limit (₦{new_credit_limit}) is less than outstanding balance '
                            f'(₦{customer.total_credit_outstanding}). Customer cannot receive additional credit.'
                        )

                    customer.credit_limit = new_credit_limit
                    customer.credit_terms_days = int(credit_terms_days) if credit_terms_days else 30
                    customer.credit_status = credit_status

                except (ValueError, TypeError):
                    messages.warning(request, '⚠️ Invalid credit values provided, keeping existing values')

            customer.save()

            messages.success(
                request,
                f'✅ Customer {customer.full_name} updated successfully'
            )
            return redirect('customers:customer_detail', pk=customer.pk)

        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    context = {
        'customer': customer,
        'edit_mode': True,
        'can_manage_credit': user_can_manage_credit(request.user),
        'sales_persons': SalesPerson.objects.filter(is_active=True).order_by('full_name'),
    }

    return render(request, 'customers/customer_form.html', context)


@login_required
@require_http_methods(["POST"])
def customer_delete(request, pk):
    """
    Soft delete customer (set is_active=False)

    URL: POST /customers/<pk>/delete/
    """
    customer = get_object_or_404(Customer, pk=pk)

    # Check if customer has outstanding balance
    if customer.total_credit_outstanding > 0:
        messages.error(
            request,
            f'❌ Cannot deactivate customer with outstanding balance of ₦{customer.total_credit_outstanding}'
        )
        return redirect('customers:customer_detail', pk=customer.pk)

    # Soft delete
    customer.is_active = False
    customer.save(update_fields=['is_active'])

    messages.success(
        request,
        f'✅ Customer {customer.full_name} deactivated'
    )

    return redirect('customers:customer_list')


@login_required
@require_http_methods(["POST"])
def refresh_customer_stats(request, pk):
    """
    Manually refresh customer statistics

    URL: POST /customers/<pk>/refresh-stats/
    """
    customer = get_object_or_404(Customer, pk=pk)

    try:
        # Update statistics
        customer.update_stats()

        messages.success(
            request,
            f'✅ Statistics refreshed for {customer.full_name}'
        )
    except Exception as e:
        messages.error(
            request,
            f'❌ Error refreshing statistics: {str(e)}'
        )

    return redirect('customers:customer_detail', pk=customer.pk)


@login_required
@require_http_methods(["POST"])
def update_credit_status(request, pk):
    """
    Update customer credit status (admin/manager only)

    URL: POST /customers/<pk>/update-credit-status/
    """
    # Permission check
    if not user_can_manage_credit(request.user):
        raise PermissionDenied("You don't have permission to manage customer credit")

    customer = get_object_or_404(Customer, pk=pk)

    try:
        data = json.loads(request.body)
        new_status = data.get('credit_status')

        if new_status not in ['APPROVED', 'SUSPENDED', 'BLOCKED']:
            return JsonResponse({
                'success': False,
                'error': 'Invalid credit status'
            })

        # Warn if blocking customer with outstanding balance
        if new_status == 'BLOCKED' and customer.total_credit_outstanding > 0:
            messages.warning(
                request,
                f'⚠️ Customer blocked with outstanding balance of ₦{customer.total_credit_outstanding}'
            )

        customer.credit_status = new_status
        customer.save(update_fields=['credit_status'])

        return JsonResponse({
            'success': True,
            'message': f'Credit status updated to {new_status}'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_http_methods(["GET"])
def credit_customers_report(request):
    """
    Report of all customers with credit (admin/manager only)

    URL: GET /customers/credit-report/
    """
    # Permission check
    if not user_can_manage_credit(request.user):
        raise PermissionDenied("You don't have permission to view credit reports")

    from apps.credit.models import CreditLedger
    from django.db.models import DecimalField
    from django.db.models.functions import Coalesce

    customers = Customer.objects.filter(
        is_active=True,
        credit_limit__gt=0
    ).annotate(
        outstanding_balance=Coalesce(
            Sum(
                'credit_ledger_entries__balance_outstanding',
                filter=Q(credit_ledger_entries__status__in=['PENDING', 'PARTIAL', 'OVERDUE'])
            ),
            Decimal('0.00'),
            output_field=DecimalField()
        )
    )

    status_filter = request.GET.get('status')
    if status_filter:
        customers = customers.filter(credit_status=status_filter)

    customers = customers.order_by('-outstanding_balance')

    total_outstanding = CreditLedger.objects.filter(
        customer__is_active=True,
        customer__credit_limit__gt=0,
        status__in=['PENDING', 'PARTIAL', 'OVERDUE']
    ).aggregate(total=Sum('balance_outstanding'))['total'] or Decimal('0.00')

    totals = customers.aggregate(total_limits=Sum('credit_limit'))

    context = {
        'customers': customers,
        'total_credit_limits': totals['total_limits'] or Decimal('0.00'),
        'total_outstanding': total_outstanding,
        'can_manage_credit': True,
    }

    return render(request, 'customers/credit_report.html', context)

# ============================================================
# SALES PERSON VIEWS
# ============================================================

def user_can_manage_sales_persons(user):
    """
    Only superusers, staff, managers, or admins can manage sales persons.
    """
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name__in=['Manager', 'Admin']).exists()


@login_required
@require_http_methods(["GET"])
def salesperson_list(request):
    """
    List all sales persons with summary stats.

    URL: GET /customers/sales-persons/
    """
    if not user_can_manage_sales_persons(request.user):
        raise PermissionDenied("You don't have permission to manage sales persons")

    sales_persons = SalesPerson.objects.prefetch_related('customers').order_by('full_name')

    search = request.GET.get('search', '').strip()
    if search:
        sales_persons = sales_persons.filter(
            Q(full_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search) |
            Q(employee_id__icontains=search)
        )

    status_filter = request.GET.get('status')
    if status_filter == 'active':
        sales_persons = sales_persons.filter(is_active=True)
    elif status_filter == 'inactive':
        sales_persons = sales_persons.filter(is_active=False)

    sales_persons = sales_persons.annotate(
        total_customers=Count('customers'),
        active_customers=Count('customers', filter=Q(customers__is_active=True)),
        total_revenue=Sum(
            'customers__total_spent',
            filter=Q(customers__is_active=True)
        )
    )

    context = {
        'sales_persons': sales_persons,
        'search': search,
        'status_filter': status_filter,
        'total_count': SalesPerson.objects.count(),
        'active_count': SalesPerson.objects.filter(is_active=True).count(),
    }

    return render(request, 'customers/salesperson_list.html', context)


@login_required
@require_http_methods(["GET"])
def salesperson_detail(request, pk):
    """
    Sales person detail — their assigned customers, stats, revenue.

    URL: GET /customers/sales-persons/<pk>/
    """
    if not user_can_manage_sales_persons(request.user):
        raise PermissionDenied("You don't have permission to view sales person details")

    sales_person = get_object_or_404(SalesPerson, pk=pk)

    customers = sales_person.customers.filter(is_active=True).order_by('-total_spent')

    stats = customers.aggregate(
        total_customers=Count('id'),
        total_revenue=Sum('total_spent'),
        total_orders=Sum('total_orders'),
        avg_spent=Avg('total_spent'),
    )

    # Credit exposure for this sales person's customers
    total_outstanding = sum(
        c.total_credit_outstanding for c in customers
    )

    context = {
        'sales_person': sales_person,
        'customers': customers,
        'stats': stats,
        'total_outstanding': total_outstanding,
        'can_manage_credit': user_can_manage_credit(request.user),
    }

    return render(request, 'customers/salesperson_detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def salesperson_create(request):
    """
    Create a new sales person.

    URL: GET/POST /customers/sales-persons/create/
    """
    if not user_can_manage_sales_persons(request.user):
        raise PermissionDenied("You don't have permission to manage sales persons")

    if request.method == 'POST':
        try:
            sales_person = SalesPersonService.create(
                full_name=request.POST.get('full_name'),
                phone=request.POST.get('phone', ''),
                email=request.POST.get('email', ''),
                employee_id=request.POST.get('employee_id', '') or None,
                user_id=request.POST.get('user_id') or None,
            )
            messages.success(request, f'✅ Sales person {sales_person.full_name} created successfully')
            return redirect('customers:salesperson_detail', pk=sales_person.pk)

        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    context = {
        'edit_mode': False,
    }

    return render(request, 'customers/salesperson_form.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def salesperson_edit(request, pk):
    """
    Edit an existing sales person.

    URL: GET/POST /customers/sales-persons/<pk>/edit/
    """
    if not user_can_manage_sales_persons(request.user):
        raise PermissionDenied("You don't have permission to manage sales persons")

    sales_person = get_object_or_404(SalesPerson, pk=pk)

    if request.method == 'POST':
        try:
            sales_person = SalesPersonService.update(
                sales_person=sales_person,
                full_name=request.POST.get('full_name'),
                phone=request.POST.get('phone', ''),
                email=request.POST.get('email', ''),
                employee_id=request.POST.get('employee_id', '') or None,
                user_id=request.POST.get('user_id') or None,
                is_active=request.POST.get('is_active') == 'on',
            )
            messages.success(request, f'✅ Sales person {sales_person.full_name} updated successfully')
            return redirect('customers:salesperson_detail', pk=sales_person.pk)

        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    context = {
        'sales_person': sales_person,
        'edit_mode': True,
    }

    return render(request, 'customers/salesperson_form.html', context)


@login_required
@require_http_methods(["POST"])
def salesperson_delete(request, pk):
    """
    Soft-delete (deactivate) a sales person.
    Customers are NOT deleted — their sales_person FK is set to NULL.

    URL: POST /customers/sales-persons/<pk>/delete/
    """
    if not user_can_manage_sales_persons(request.user):
        raise PermissionDenied("You don't have permission to manage sales persons")

    sales_person = get_object_or_404(SalesPerson, pk=pk)

    try:
        customer_count = SalesPersonService.deactivate(sales_person)
        messages.success(
            request,
            f'✅ {sales_person.full_name} deactivated. '
            f'{customer_count} customer(s) unassigned.'
        )
    except Exception as e:
        messages.error(request, f'❌ Error: {str(e)}')

    return redirect('customers:salesperson_list')


@login_required
@require_http_methods(["POST"])
def salesperson_reassign_customers(request, pk):
    """
    Reassign all customers from one sales person to another.

    URL: POST /customers/sales-persons/<pk>/reassign/
    Body: { "to_id": <int> }
    """
    if not user_can_manage_sales_persons(request.user):
        raise PermissionDenied("You don't have permission to manage sales persons")

    sales_person = get_object_or_404(SalesPerson, pk=pk)

    try:
        data = json.loads(request.body)
        to_id = data.get('to_id')

        if not to_id:
            return JsonResponse({'success': False, 'error': 'Target sales person required'})

        to_sp = get_object_or_404(SalesPerson, pk=to_id, is_active=True)
        moved = SalesPersonService.reassign_customers(from_sp=sales_person, to_sp=to_sp)

        return JsonResponse({
            'success': True,
            'moved': moved,
            'message': f'{moved} customer(s) reassigned to {to_sp.full_name}'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def salesperson_search_api(request):
    """
    JSON search for active sales persons (used in customer form dropdowns).

    URL: GET /customers/sales-persons/search/?q=<query>
    """
    query = request.GET.get('q', '').strip()
    sales_persons = SalesPerson.objects.filter(is_active=True)

    if query:
        sales_persons = sales_persons.filter(
            Q(full_name__icontains=query) |
            Q(employee_id__icontains=query)
        )

    data = [
        {
            'id': sp.pk,
            'full_name': sp.full_name,
            'employee_id': sp.employee_id or '',
            'phone': sp.phone or '',
        }
        for sp in sales_persons.order_by('full_name')[:20]
    ]

    return JsonResponse({'results': data})