from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import json


def index(request):
    return render(request, 'accounts/login.html')


@login_required
def dashboard(request):
    """
    Dashboard with real-time business metrics
    """
    from apps.orders.models import Order, OrderItem
    from apps.customers.models import Customer
    from apps.catalog.models import ProductVariant
    from apps.receipts.models import Receipt

    # ── Date Ranges ──────────────────────────────────────────────────────
    now = timezone.now()
    today = now.date()

    # Today
    today_start = timezone.make_aware(
        timezone.datetime.combine(today, timezone.datetime.min.time())
    )

    # Yesterday (for % change comparison)
    yesterday = today - timedelta(days=1)
    yesterday_start = timezone.make_aware(
        timezone.datetime.combine(yesterday, timezone.datetime.min.time())
    )
    yesterday_end = today_start

    # ── 1. Total Revenue (Today) ─────────────────────────────────────────
    today_revenue = Order.objects.filter(
        status__in=['CONFIRMED', 'COMPLETED'],
        created_at__gte=today_start,
    ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

    yesterday_revenue = Order.objects.filter(
        status__in=['CONFIRMED', 'COMPLETED'],
        created_at__gte=yesterday_start,
        created_at__lt=yesterday_end,
    ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

    if yesterday_revenue > 0:
        revenue_change = ((today_revenue - yesterday_revenue) / yesterday_revenue) * 100
    else:
        revenue_change = 100 if today_revenue > 0 else 0

    # ── 2. Total Sales (Orders Today) ────────────────────────────────────
    today_sales = Order.objects.filter(
        status__in=['CONFIRMED', 'COMPLETED'],
        created_at__gte=today_start,
    ).count()

    yesterday_sales = Order.objects.filter(
        status__in=['CONFIRMED', 'COMPLETED'],
        created_at__gte=yesterday_start,
        created_at__lt=yesterday_end,
    ).count()

    if yesterday_sales > 0:
        sales_change = ((today_sales - yesterday_sales) / yesterday_sales) * 100
    else:
        sales_change = 100 if today_sales > 0 else 0

    # ── 3. Total Customers ───────────────────────────────────────────────
    total_customers = Customer.objects.filter(is_active=True).count()

    # New customers today
    new_customers_today = Customer.objects.filter(
        created_at__gte=today_start,
        is_active=True,
    ).count()

    # New customers yesterday
    new_customers_yesterday = Customer.objects.filter(
        created_at__gte=yesterday_start,
        created_at__lt=yesterday_end,
        is_active=True,
    ).count()

    if new_customers_yesterday > 0:
        customers_change = ((new_customers_today - new_customers_yesterday) / new_customers_yesterday) * 100
    else:
        customers_change = 100 if new_customers_today > 0 else 0

    # ── 4. Products in Stock ─────────────────────────────────────────────
    products_in_stock = ProductVariant.objects.filter(
        is_active=True,
        stock_quantity__gt=0,
    ).count()

    products_out_of_stock = ProductVariant.objects.filter(
        is_active=True,
        stock_quantity=0,
    ).count()

    products_low_stock = ProductVariant.objects.filter(
        is_active=True,
        stock_quantity__gt=0,
        stock_quantity__lte=F('low_stock_threshold'),
    ).count()

    # Mock % change (you'd need historical tracking for real change)
    stock_change = 0

    # ── 5. Sales Chart Data (Last 7 Days) ───────────────────────────────
    sales_chart_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_start = timezone.make_aware(
            timezone.datetime.combine(day, timezone.datetime.min.time())
        )
        day_end = day_start + timedelta(days=1)

        day_revenue = Order.objects.filter(
            status__in=['CONFIRMED', 'COMPLETED'],
            created_at__gte=day_start,
            created_at__lt=day_end,
        ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

        sales_chart_data.append({
            'date': day.strftime('%b %d'),
            'revenue': float(day_revenue),
        })

    # ── 6. Recent Activity ───────────────────────────────────────────────
    recent_activities = []

    # Recent receipts
    recent_receipts = Receipt.objects.select_related('order').order_by('-created_at')[:3]
    for receipt in recent_receipts:
        recent_activities.append({
            'icon': 'fa-dollar-sign',
            'title': 'New sale recorded',
            'meta': f'Order {receipt.order.order_number} - ₦{receipt.order.total:,.0f}',
            'time': receipt.created_at,
        })

    # Recent customers
    recent_customers = Customer.objects.filter(is_active=True).order_by('-created_at')[:2]
    for customer in recent_customers:
        recent_activities.append({
            'icon': 'fa-user-plus',
            'title': 'New customer',
            'meta': f'{customer.full_name} registered',
            'time': customer.created_at,
        })

    # Sort by time descending
    recent_activities.sort(key=lambda x: x['time'], reverse=True)
    recent_activities = recent_activities[:3]

    # ── 7. Recent Orders ─────────────────────────────────────────────────
    recent_orders = Order.objects.filter(
        status__in=['CONFIRMED', 'COMPLETED', 'CANCELLED'],
    ).select_related('customer').prefetch_related('items').order_by('-created_at')[:5]

    orders_list = []
    for order in recent_orders:
        first_item = order.items.first()
        orders_list.append({
            'id': order.id,
            'order_number': order.order_number,
            'product_name': first_item.product_name if first_item else 'No items',
            'customer_name': order.customer.full_name if order.customer else 'Walk-in Customer',
            'date': order.created_at,
            'total': order.total,
            'status': order.status,
            'status_display': order.get_status_display(),
        })

    # ── Context ──────────────────────────────────────────────────────────
    context = {
        'user': request.user,

        # Stats
        'today_revenue': today_revenue,
        'revenue_change': abs(revenue_change),
        'revenue_change_positive': revenue_change >= 0,

        'today_sales': today_sales,
        'sales_change': abs(sales_change),
        'sales_change_positive': sales_change >= 0,

        'total_customers': total_customers,
        'customers_change': abs(customers_change),
        'customers_change_positive': customers_change >= 0,

        'products_in_stock': products_in_stock,
        'products_out_of_stock': products_out_of_stock,
        'products_low_stock': products_low_stock,
        'stock_change': abs(stock_change),
        'stock_change_positive': stock_change >= 0,

        # Charts & lists
        'sales_chart_data': json.dumps(sales_chart_data),
        'recent_activities': recent_activities,
        'recent_orders': orders_list,
    }

    return render(request, 'core/dashboard.html', context)