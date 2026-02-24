# apps/reports/views.py
# COMPLETE REPORTS VIEWS - AUTO-GENERATES REPORTS ON-DEMAND
# User never needs shell access - everything works from the UI

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from datetime import datetime, timedelta
import calendar
import json
import logging

from .models import (
    DailySalesReport,
    WeeklySalesReport,
    MonthlySalesReport,
    YearlySalesReport,
)
from .services import ReportService

logger = logging.getLogger(__name__)


# ============================================================================
# DASHBOARD - AUTO-GENERATES IF MISSING
# ============================================================================

@login_required
@require_http_methods(["GET"])
def reports_dashboard(request):
    """
    Reports dashboard - shows overview and links to all reports.
    AUTO-GENERATES yesterday's report if it doesn't exist.
    """
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    current_year = today.year
    current_month = today.month

    # ── AUTO-GENERATE yesterday's report if missing ────────────────────
    latest_daily = DailySalesReport.objects.filter(
        report_date=yesterday
    ).first()

    if not latest_daily:
        # Auto-generate silently in background
        try:
            latest_daily = ReportService.generate_daily_report(
                report_date=yesterday,
                user=request.user
            )
            logger.info(f"Auto-generated daily report for {yesterday}")
        except Exception as e:
            logger.error(f"Failed to auto-generate daily report: {e}")

    # Get latest reports of each type
    latest_weekly = WeeklySalesReport.objects.order_by('-year', '-week_number').first()
    latest_monthly = MonthlySalesReport.objects.order_by('-year', '-month').first()
    latest_yearly = YearlySalesReport.objects.order_by('-year').first()

    # ── Live stats from Orders (last 30 days) ──────────────────────────
    from apps.orders.models import Order

    thirty_days_ago = today - timedelta(days=30)
    thirty_days_ago_start = timezone.make_aware(
        timezone.datetime.combine(thirty_days_ago, timezone.datetime.min.time())
    )

    recent_orders = Order.objects.filter(
        status__in=['CONFIRMED', 'COMPLETED'],
        created_at__gte=thirty_days_ago_start
    )

    last_30_days_stats = recent_orders.aggregate(
        total_sales_sum=Sum('total'),
        total_orders_sum=Count('id'),
        avg_daily_sales=Avg('total')
    )

    # Convert None to 0
    for key in ['total_sales_sum', 'total_orders_sum', 'avg_daily_sales']:
        if not last_30_days_stats.get(key):
            last_30_days_stats[key] = 0

    # ── Chart data (last 30 days from Orders) ──────────────────────────
    chart_data = []
    for i in range(30):
        date = today - timedelta(days=29 - i)
        date_start = timezone.make_aware(
            timezone.datetime.combine(date, timezone.datetime.min.time())
        )
        date_end = date_start + timedelta(days=1)

        day_orders = Order.objects.filter(
            status__in=['CONFIRMED', 'COMPLETED'],
            created_at__gte=date_start,
            created_at__lt=date_end
        )

        day_total = day_orders.aggregate(total=Sum('total'))['total'] or 0

        chart_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'sales': float(day_total),
            'orders': day_orders.count()
        })

    context = {
        'latest_daily': latest_daily,
        'latest_weekly': latest_weekly,
        'latest_monthly': latest_monthly,
        'latest_yearly': latest_yearly,
        'current_year': current_year,
        'current_month': current_month,
        'last_30_days_stats': last_30_days_stats,
        'chart_data_json': json.dumps(chart_data),
    }

    return render(request, 'reports/reports_dashboard.html', context)


# ============================================================================
# DAILY REPORT - AUTO-GENERATES IF MISSING
# ============================================================================

@login_required
@require_http_methods(["GET"])
def daily_report_view(request):
    """
    Daily report view - AUTO-GENERATES if report doesn't exist.
    User just picks a date and sees the report instantly.
    """
    # Get date from query param or default to yesterday
    date_str = request.GET.get('date')
    if date_str:
        try:
            report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            report_date = (timezone.now() - timedelta(days=1)).date()
    else:
        report_date = (timezone.now() - timedelta(days=1)).date()

    # ── AUTO-GENERATE if missing ───────────────────────────────────────
    try:
        report = DailySalesReport.objects.get(report_date=report_date)
    except DailySalesReport.DoesNotExist:
        # Auto-generate on-the-fly
        report = ReportService.generate_daily_report(
            report_date=report_date,
            user=request.user
        )

    # Prepare chart data
    hourly_data = report.report_data.get('hourly_sales', [])
    payment_breakdown = report.report_data.get('payment_breakdown', {})

    # Get list of available dates (last 60 days)
    available_dates = []
    for i in range(60):
        date = timezone.now().date() - timedelta(days=i)
        available_dates.append(date)

    context = {
        'report': report,
        'available_dates': available_dates,
        'hourly_data_json': json.dumps(hourly_data),
        'payment_data_json': json.dumps(payment_breakdown),
    }

    return render(request, 'reports/daily_report.html', context)


# ============================================================================
# WEEKLY REPORT - AUTO-GENERATES IF MISSING
# ============================================================================

@login_required
@require_http_methods(["GET"])
def weekly_report_view(request):
    """Weekly report - AUTO-GENERATES if missing"""
    today = timezone.now().date()
    year = int(request.GET.get('year', today.year))
    week_number = int(request.GET.get('week', today.isocalendar()[1]))

    # ── AUTO-GENERATE if missing ───────────────────────────────────────
    try:
        report = WeeklySalesReport.objects.get(year=year, week_number=week_number)
    except WeeklySalesReport.DoesNotExist:
        report = ReportService.generate_weekly_report(
            year=year,
            week_number=week_number,
            user=request.user
        )

    # Get available weeks (last 52)
    available_weeks = []
    for i in range(52):
        date = today - timedelta(weeks=i)
        iso_year, iso_week, _ = date.isocalendar()
        available_weeks.append({
            'year': iso_year,
            'week_number': iso_week,
            'week_start_date': date
        })

    daily_breakdown = report.report_data.get('daily_breakdown', [])

    context = {
        'report': report,
        'available_weeks': available_weeks,
        'daily_data_json': json.dumps(daily_breakdown),
    }

    return render(request, 'reports/weekly_report.html', context)


# ============================================================================
# MONTHLY REPORT - AUTO-GENERATES IF MISSING
# ============================================================================

@login_required
@require_http_methods(["GET"])
def monthly_report_view(request):
    """Monthly report - AUTO-GENERATES if missing"""
    today = timezone.now().date()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    # ── AUTO-GENERATE if missing ───────────────────────────────────────
    try:
        report = MonthlySalesReport.objects.get(year=year, month=month)
    except MonthlySalesReport.DoesNotExist:
        report = ReportService.generate_monthly_report(
            year=year,
            month=month,
            user=request.user
        )

    # Get available months (last 24)
    available_months = []
    for i in range(24):
        date = today - timedelta(days=i * 30)
        available_months.append({
            'year': date.year,
            'month': date.month,
            'month_name': calendar.month_name[date.month]
        })

    daily_breakdown = report.report_data.get('daily_breakdown', [])

    context = {
        'report': report,
        'available_months': available_months,
        'month_name': calendar.month_name[month],
        'daily_data_json': json.dumps(daily_breakdown),
    }

    return render(request, 'reports/monthly_report.html', context)


# ============================================================================
# YEARLY REPORT - AUTO-GENERATES IF MISSING
# ============================================================================

@login_required
@require_http_methods(["GET"])
def yearly_report_view(request):
    """Yearly report - AUTO-GENERATES if missing"""
    year = int(request.GET.get('year', timezone.now().year))

    # ── AUTO-GENERATE if missing ───────────────────────────────────────
    try:
        report = YearlySalesReport.objects.get(year=year)
    except YearlySalesReport.DoesNotExist:
        report = ReportService.generate_yearly_report(
            year=year,
            user=request.user
        )

    # Get available years
    from apps.orders.models import Order
    first_order = Order.objects.order_by('created_at').first()
    current_year = timezone.now().year

    if first_order:
        start_year = first_order.created_at.year
    else:
        start_year = current_year

    available_years = list(range(current_year, start_year - 1, -1))

    monthly_breakdown = report.report_data.get('monthly_breakdown', [])

    context = {
        'report': report,
        'available_years': available_years,
        'monthly_data_json': json.dumps(monthly_breakdown),
    }

    return render(request, 'reports/yearly_report.html', context)


# ============================================================================
# CUSTOM REPORT - ALWAYS LIVE DATA
# ============================================================================

@login_required
@require_http_methods(["GET"])
def custom_report_view(request):
    """
    Custom date range report - ALWAYS uses live Order data.
    No pre-generation needed.
    """
    start_date_str = request.GET.get('start')
    end_date_str = request.GET.get('end')

    if not start_date_str or not end_date_str:
        # Show form
        return render(request, 'reports/custom_report_form.html')

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return HttpResponse("Invalid date format", status=400)

    # Get LIVE orders in range
    from apps.orders.models import Order, OrderPayment

    start_datetime = timezone.make_aware(
        timezone.datetime.combine(start_date, timezone.datetime.min.time())
    )
    end_datetime = timezone.make_aware(
        timezone.datetime.combine(end_date, timezone.datetime.max.time())
    )

    orders = Order.objects.filter(
        status__in=['CONFIRMED', 'COMPLETED'],
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    )

    # Calculate metrics from LIVE data
    aggregates = orders.aggregate(
        total_sales=Sum('total'),
        total_orders=Count('id'),
        avg_order_value=Avg('total'),
        gross_sales=Sum('subtotal'),
        total_discounts=Sum('discount_amount'),
        total_tax=Sum('tax_amount'),
    )

    # Count total items from OrderItem (not a field on Order)
    from apps.orders.models import OrderItem
    total_items = OrderItem.objects.filter(order__in=orders).aggregate(
        total=Sum('quantity')
    )['total'] or 0
    aggregates['total_items'] = total_items

    # Convert None to 0
    for key, value in aggregates.items():
        if value is None:
            aggregates[key] = 0

    # Payment breakdown
    payments = OrderPayment.objects.filter(
        order__in=orders
    ).values('payment_method').annotate(total=Sum('amount'))

    payment_breakdown = {}
    for payment in payments:
        payment_breakdown[payment['payment_method']] = payment['total']

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'aggregates': aggregates,
        'payment_breakdown': payment_breakdown,
        'days_count': (end_date - start_date).days + 1,
    }

    return render(request, 'reports/custom_report.html', context)


# ============================================================================
# EXPORT FUNCTIONS
# ============================================================================

@login_required
@require_http_methods(["GET"])
def export_report_pdf(request, report_type, report_id):
    """Export report as PDF"""
    from .utils import generate_pdf_report

    try:
        if report_type == 'daily':
            report = get_object_or_404(DailySalesReport, pk=report_id)
            filename = f"daily_report_{report.report_date}.pdf"
        elif report_type == 'weekly':
            report = get_object_or_404(WeeklySalesReport, pk=report_id)
            filename = f"weekly_report_W{report.week_number}_{report.year}.pdf"
        elif report_type == 'monthly':
            report = get_object_or_404(MonthlySalesReport, pk=report_id)
            filename = f"monthly_report_{report.month_name}_{report.year}.pdf"
        elif report_type == 'yearly':
            report = get_object_or_404(YearlySalesReport, pk=report_id)
            filename = f"yearly_report_{report.year}.pdf"
        else:
            return HttpResponse("Invalid report type", status=400)

        pdf_content = generate_pdf_report(report, report_type)

        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        logger.exception(f"Error exporting PDF: {e}")
        return HttpResponse(f"Error generating PDF: {str(e)}", status=500)


@login_required
@require_http_methods(["GET"])
def export_report_excel(request, report_type, report_id):
    """Export report as Excel"""
    from .utils import generate_excel_report

    try:
        if report_type == 'daily':
            report = get_object_or_404(DailySalesReport, pk=report_id)
            filename = f"daily_report_{report.report_date}.xlsx"
        elif report_type == 'monthly':
            report = get_object_or_404(MonthlySalesReport, pk=report_id)
            filename = f"monthly_report_{report.month_name}_{report.year}.xlsx"
        elif report_type == 'yearly':
            report = get_object_or_404(YearlySalesReport, pk=report_id)
            filename = f"yearly_report_{report.year}.xlsx"
        else:
            return HttpResponse("Invalid report type", status=400)

        excel_content = generate_excel_report(report, report_type)

        response = HttpResponse(
            excel_content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        logger.exception(f"Error exporting Excel: {e}")
        return HttpResponse(f"Error generating Excel: {str(e)}", status=500)