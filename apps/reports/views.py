# apps/reports/views.py - Comprehensive Report Views
import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from datetime import datetime, timedelta, date
import calendar

from .services import ReportService, get_today_sales, get_week_sales, get_month_sales
from .models import DailySalesReport, MonthlySalesReport, YearlySalesReport
from django.db import models
from apps.catalog.models import Product, Category
from apps.orders.models import Order, OrderItem


@login_required
@login_required
def reports_dashboard(request):

    today = timezone.now().date()
    last_30_start = today - timedelta(days=30)

    last_30_days_stats = ReportService.get_sales_analytics(
        last_30_start,
        today
    )

    latest_daily = DailySalesReport.objects.order_by('-report_date').first()
    latest_monthly = MonthlySalesReport.objects.order_by('-year', '-month').first()

    chart_data = ReportService.get_daily_breakdown(last_30_start, today)

    context = {
        "last_30_days_stats": last_30_days_stats,
        "latest_daily": latest_daily,
        "latest_monthly": latest_monthly,
        "chart_data_json": json.dumps([
            {
                "date": d["day"].strftime("%Y-%m-%d"),
                "sales": float(d["total_sales"] or 0)
            }
            for d in chart_data
        ])
    }

    return render(request, "reports/reports_dashboard.html", context)


@login_required
def daily_report_view(request):
    """
    Daily report view with date selector
    """
    # Get date from request or default to yesterday
    date_str = request.GET.get('date')
    if date_str:
        report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        report_date = (timezone.now() - timedelta(days=1)).date()

    # Get or generate report
    report = ReportService.get_daily_report(report_date)

    # Get live analytics (for today)
    if report_date == timezone.now().date():
        live_analytics = ReportService.get_sales_analytics(report_date, report_date)
    else:
        live_analytics = None

    # Navigation dates
    prev_date = report_date - timedelta(days=1)
    next_date = report_date + timedelta(days=1)
    can_go_next = next_date < timezone.now().date()

    context = {
        'report': report,
        'live_analytics': live_analytics,
        'report_date': report_date,
        'prev_date': prev_date,
        'next_date': next_date,
        'can_go_next': can_go_next,
        'is_today': report_date == timezone.now().date(),
    }

    return render(request, 'reports/daily_report.html', context)


@login_required
def weekly_report_view(request):
    """
    Weekly report view
    """
    # Get week from request or default to current week
    date_str = request.GET.get('date')
    if date_str:
        reference_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        reference_date = timezone.now().date()

    # Calculate week start (Monday)
    week_start = reference_date - timedelta(days=reference_date.weekday())
    week_end = week_start + timedelta(days=6)

    # Get analytics
    analytics = ReportService.get_sales_analytics(week_start, week_end)

    # Get daily breakdown
    daily_breakdown = ReportService.get_daily_breakdown(week_start, week_end)

    # Get product performance
    top_products = ReportService.get_product_performance(week_start, week_end)[:10]

    # Navigation
    prev_week_start = week_start - timedelta(days=7)
    next_week_start = week_start + timedelta(days=7)
    can_go_next = next_week_start <= timezone.now().date()

    context = {
        'analytics': analytics,
        'daily_breakdown': daily_breakdown,
        'top_products': top_products,
        'week_start': week_start,
        'week_end': week_end,
        'prev_week_start': prev_week_start,
        'next_week_start': next_week_start,
        'can_go_next': can_go_next,
    }

    return render(request, 'reports/weekly_report.html', context)


@login_required
def monthly_report_view(request):
    """
    Monthly report view
    """
    # Get month/year from request or default to current month
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))

    # Get or generate report
    report = ReportService.get_monthly_report(year, month)

    # Get category performance
    start_date = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = date(year, month, last_day)

    category_performance = ReportService.get_category_performance(start_date, end_date)
    top_products = ReportService.get_product_performance(start_date, end_date)[:15]

    # Navigation
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    today = timezone.now().date()
    can_go_next = date(next_year, next_month, 1) <= date(today.year, today.month, 1)

    context = {
        'report': report,
        'category_performance': category_performance,
        'top_products': top_products,
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'can_go_next': can_go_next,
    }

    return render(request, 'reports/monthly_report.html', context)


@login_required
def yearly_report_view(request):
    """
    Yearly report view
    """
    # Get year from request or default to current year
    year = int(request.GET.get('year', timezone.now().year))

    # Get or generate report
    report = ReportService.get_yearly_report(year)

    # Get category performance
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    category_performance = ReportService.get_category_performance(start_date, end_date)
    top_products = ReportService.get_product_performance(start_date, end_date)[:20]

    # Navigation
    prev_year = year - 1
    next_year = year + 1
    can_go_next = next_year <= timezone.now().year

    context = {
        'report': report,
        'category_performance': category_performance,
        'top_products': top_products,
        'year': year,
        'prev_year': prev_year,
        'next_year': next_year,
        'can_go_next': can_go_next,
    }

    return render(request, 'reports/yearly_report.html', context)


@login_required
def custom_report_view(request):
    """
    Custom period report with flexible date range
    """
    if request.method == 'POST':
        # Get date range from form
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

            # Validate dates
            if start_date > end_date:
                messages.error(request, 'Start date must be before end date')
                return redirect('reports:custom_report')

            if end_date > timezone.now().date():
                messages.error(request, 'End date cannot be in the future')
                return redirect('reports:custom_report')

            # Generate report
            include_comparison = request.POST.get('include_comparison') == 'on'
            report = ReportService.generate_custom_report(
                start_date,
                end_date,
                include_comparisons=include_comparison
            )

            # Get product details
            product_id = request.POST.get('product_id')
            variant_id = request.POST.get('variant_id')

            if product_id:
                product_performance = ReportService.get_product_performance(
                    start_date, end_date,
                    product_id=int(product_id) if product_id else None,
                    variant_id=int(variant_id) if variant_id else None
                )
                report['product_performance_detail'] = product_performance

            context = {
                'report': report,
                'start_date': start_date,
                'end_date': end_date,
                'include_comparison': include_comparison,
            }

            return render(request, 'reports/custom_report_results.html', context)

        except ValueError as e:
            messages.error(request, f'Invalid date format: {str(e)}')
            return redirect('reports:custom_report')

    # GET request - show form
    # Default to last 30 days
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)

    # Get products for dropdown
    from apps.catalog.models import Product
    products = Product.objects.filter(is_active=True).order_by('name')

    context = {
        'default_start': start_date,
        'default_end': end_date,
        'products': products,
    }

    return render(request, 'reports/custom_report_form.html', context)


# ============================================
# PRODUCT SPECIFIC REPORTS
# ============================================

@login_required
def product_performance_report(request, product_id):
    """
    Detailed performance report for a specific product
    """
    from apps.catalog.models import Product

    product = Product.objects.get(pk=product_id)

    # Get date range
    date_str = request.GET.get('period', '30')
    days = int(date_str)

    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)

    # Get performance data
    performance = ReportService.get_product_performance(
        start_date, end_date,
        product_id=product_id
    )

    # Get daily breakdown
    from apps.orders.models import Order, OrderItem

    orders = Order.objects.filter(
        status='COMPLETED',
        completed_at__date__gte=start_date,
        completed_at__date__lte=end_date
    )

    daily_sales = OrderItem.objects.filter(
        order__in=orders,
        product_id=product_id
    ).extra(
        select={'day': 'DATE(order__completed_at)'}
    ).values('day').annotate(
        units_sold=models.Sum('quantity'),
        revenue=models.Sum(models.F('quantity') * models.F('unit_price'))
    ).order_by('day')

    context = {
        'product': product,
        'performance': performance,
        'daily_sales': list(daily_sales),
        'start_date': start_date,
        'end_date': end_date,
        'period_days': days,
    }

    return render(request, 'reports/product_performance.html', context)


# ============================================
# API ENDPOINTS (for AJAX/charts)
# ============================================

@login_required
def sales_chart_data(request):
    """
    Return sales data for charts (JSON)
    """
    period = request.GET.get('period', 'week')

    today = timezone.now().date()

    if period == 'today':
        start_date = today
        end_date = today
        breakdown = ReportService.get_hourly_breakdown(today)
        labels = [f"{h['hour']}:00" for h in breakdown]
        data = [float(h['total_sales']) for h in breakdown]

    elif period == 'week':
        start_date = today - timedelta(days=6)
        end_date = today
        breakdown = ReportService.get_daily_breakdown(start_date, end_date)
        labels = [b['day'].strftime('%a') for b in breakdown]
        data = [float(b['total_sales']) for b in breakdown]

    elif period == 'month':
        start_date = today.replace(day=1)
        end_date = today
        breakdown = ReportService.get_daily_breakdown(start_date, end_date)
        labels = [b['day'].strftime('%d') for b in breakdown]
        data = [float(b['total_sales']) for b in breakdown]

    else:
        start_date = today.replace(month=1, day=1)
        end_date = today
        monthly_data = []
        for month in range(1, 13):
            month_start = date(today.year, month, 1)
            month_end = date(today.year, month, calendar.monthrange(today.year, month)[1])
            if month_end > today:
                month_end = today
            analytics = ReportService.get_sales_analytics(month_start, month_end)
            monthly_data.append({
                'month': calendar.month_abbr[month],
                'sales': float(analytics['total_sales'])
            })
        labels = [m['month'] for m in monthly_data]
        data = [m['sales'] for m in monthly_data]

    return JsonResponse({
        'labels': labels,
        'data': data,
        'period': period
    })


@login_required
def export_report_pdf(request, report_type, report_id):
    """
    Export report as PDF
    """
    # TODO: Implement PDF export using ReportLab or WeasyPrint
    messages.info(request, 'PDF export coming soon')
    return redirect('reports:reports_dashboard')


@login_required
def export_report_excel(request, report_type, report_id):
    """
    Export report as Excel
    """
    # TODO: Implement Excel export using openpyxl
    messages.info(request, 'Excel export coming soon')
    return redirect('reports:reports_dashboard')


@login_required
def top_products_report(request):
    """
    Top selling products report
    """
    # Get period from request
    period = request.GET.get('period', '30')
    days = int(period) if period.isdigit() else 30

    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)

    # Get top products
    top_by_revenue = ReportService.get_product_performance(start_date, end_date)[:20]

    # Get top by quantity
    orders = Order.objects.filter(
        status='COMPLETED',
        completed_at__date__gte=start_date,
        completed_at__date__lte=end_date
    )

    top_by_quantity = OrderItem.objects.filter(
        order__in=orders
    ).values(
        'product_id',
        'product__name',
        'product__category__name'
    ).annotate(
        units_sold=models.Sum('quantity'),
        total_revenue=models.Sum(models.F('quantity') * models.F('unit_price'))
    ).order_by('-units_sold')[:20]

    # Get category summary
    category_performance = ReportService.get_category_performance(start_date, end_date)

    context = {
        'top_by_revenue': top_by_revenue,
        'top_by_quantity': top_by_quantity,
        'category_performance': category_performance,
        'start_date': start_date,
        'end_date': end_date,
        'period_days': days,
        'period_options': [7, 14, 30, 60, 90],
    }

    return render(request, 'reports/top_products.html', context)


@login_required
def category_report(request):
    """
    Category performance report
    """
    # Get period from request
    period = request.GET.get('period', '30')
    days = int(period) if period.isdigit() else 30

    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)

    # Get category performance
    categories = ReportService.get_category_performance(start_date, end_date)

    # Get total for percentage calculations
    total_revenue = sum(c['total_revenue'] for c in categories)

    # Add percentage
    for cat in categories:
        if total_revenue > 0:
            cat['percentage'] = (cat['total_revenue'] / total_revenue) * 100
        else:
            cat['percentage'] = 0

    context = {
        'categories': categories,
        'total_revenue': total_revenue,
        'start_date': start_date,
        'end_date': end_date,
        'period_days': days,
    }

    return render(request, 'reports/category_report.html', context)


@login_required
def quick_stats_api(request):
    """
    Quick stats API for dashboard widgets
    Returns JSON with current stats
    """
    today = timezone.now().date()

    # Get today, week, month stats
    today_stats = ReportService.get_sales_analytics(today, today)

    week_start = today - timedelta(days=today.weekday())
    week_stats = ReportService.get_sales_analytics(week_start, today)

    month_start = today.replace(day=1)
    month_stats = ReportService.get_sales_analytics(month_start, today)

    return JsonResponse({
        'today': {
            'sales': float(today_stats['total_sales']),
            'orders': today_stats['total_orders'],
            'items': today_stats['total_items_sold'],
            'customers': today_stats['total_customers'],
        },
        'week': {
            'sales': float(week_stats['total_sales']),
            'orders': week_stats['total_orders'],
            'average_order': float(week_stats['average_order_value']),
        },
        'month': {
            'sales': float(month_stats['total_sales']),
            'orders': month_stats['total_orders'],
            'customers': month_stats['total_customers'],
            'new_customers': month_stats['new_customers'],
        }
    })


@login_required
def export_custom_report(request):
    """
    Export custom report as CSV
    """
    if request.method != 'POST':
        return redirect('reports:custom_report')

    import csv
    from django.http import HttpResponse

    # Get dates from POST
    start_date = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%d').date()
    end_date = datetime.strptime(request.POST.get('end_date'), '%Y-%m-%d').date()

    # Generate report
    report = ReportService.generate_custom_report(start_date, end_date, include_comparisons=False)

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="sales_report_{start_date}_{end_date}.csv"'

    writer = csv.writer(response)

    # Write headers
    writer.writerow(['Sales Report'])
    writer.writerow(['Period', f'{start_date} to {end_date}'])
    writer.writerow([])

    # Write summary
    writer.writerow(['Metric', 'Value'])
    writer.writerow(['Total Sales', f"₦{report['total_sales']}"])
    writer.writerow(['Total Orders', report['total_orders']])
    writer.writerow(['Total Items', report['total_items_sold']])
    writer.writerow(['Average Order Value', f"₦{report['average_order_value']}"])
    writer.writerow(['Total Customers', report['total_customers']])
    writer.writerow(['New Customers', report['new_customers']])
    writer.writerow([])

    # Write daily breakdown
    writer.writerow(['Daily Breakdown'])
    writer.writerow(['Date', 'Sales', 'Orders', 'Items', 'Average Order'])
    for day in report['daily_breakdown']:
        writer.writerow([
            day['day'],
            f"₦{day['total_sales']}",
            day['total_orders'],
            day['total_items'],
            f"₦{day['average_order']}"
        ])

    return response