# apps/customers/views.py - Complete Customer Views with Dashboard

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Sum, Count, Avg, F
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import json

from .models import Customer
from .services import CustomerService




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

    context = {
        'customer': customer,
        'orders': orders,
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
            customer = CustomerService.create_customer(
                full_name=request.POST.get('full_name'),
                phone=request.POST.get('phone', ''),
                email=request.POST.get('email', ''),
                customer_type=request.POST.get('customer_type', 'INDIVIDUAL'),
                address_line=request.POST.get('address_line', ''),
                city=request.POST.get('city', ''),
                state=request.POST.get('state', ''),
                created_by=request.user
            )

            messages.success(
                request,
                f'✅ Customer {customer.full_name} created successfully'
            )
            return redirect('customers:customer_detail', pk=customer.pk)

        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')

    return render(request, 'customers/customer_form.html')


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
            # Update fields
            customer.full_name = request.POST.get('full_name')
            customer.phone = request.POST.get('phone', '')
            customer.email = request.POST.get('email', '')
            customer.customer_type = request.POST.get('customer_type')
            customer.address_line = request.POST.get('address_line', '')
            customer.city = request.POST.get('city', '')
            customer.state = request.POST.get('state', '')

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


