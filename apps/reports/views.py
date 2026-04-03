# apps/reports/views.py

from datetime import date
from django.shortcuts import render, get_object_or_404, redirect
from django.http import FileResponse, JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib import messages

from .models import ReportTemplate, GeneratedReport
from .services import ReportService


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_date(value, fallback: date) -> date:
    if not value:
        return fallback
    try:
        from datetime import datetime
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return fallback


# ── Dashboard ────────────────────────────────────────────────────────────────

@login_required
def reports_dashboard(request):
    context = ReportService.build_dashboard_context(request.user)
    return render(request, "reports/reports_dashboard.html", context)


# ── Generate (existing template-based reports) ────────────────────────────────

@login_required
def generate_report(request, report_type):
    template = get_object_or_404(
        ReportTemplate,
        report_type=report_type,
        is_active=True
    )

    if request.method == "POST":
        date_from   = request.POST.get("date_from")
        date_to     = request.POST.get("date_to")
        file_format = request.POST.get("format", "EXCEL")

        report = ReportService.generate_report(
            report_template=template,
            generated_by=request.user,
            date_from=date_from,
            date_to=date_to,
            file_format=file_format
        )

        return redirect("reports:download_report", pk=report.pk)

    context = {
        "template":     template,
        "default_from": timezone.now().date(),
        "default_to":   timezone.now().date(),
    }
    return render(request, "reports/generate_form.html", context)


# ── Download (existing generated report file) ────────────────────────────────

@login_required
def download_report(request, pk):
    report = get_object_or_404(GeneratedReport, pk=pk)
    if not report.file_path:
        return redirect("reports:dashboard")
    return FileResponse(
        report.file_path.open("rb"),
        as_attachment=True,
        filename=report.file_path.name.split("/")[-1]
    )


# ── Report History ────────────────────────────────────────────────────────────

@login_required
def report_history(request):
    reports = GeneratedReport.objects.select_related(
        "report_template"
    ).order_by("-generated_at")

    paginator = Paginator(reports, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "reports/history.html", {
        "reports":  page_obj,
        "page_obj": page_obj,
    })


# ── Quick stats API ────────────────────────────────────────────────────────────

@login_required
def quick_reports_api(request):
    today = timezone.now().date()
    data = {
        "today_sales":  ReportService.get_sales_analytics(today, today),
        "inventory":    ReportService.get_inventory_summary(today),
        "best_sellers": ReportService.get_best_sellers(today),
    }
    return JsonResponse(data)


# ════════════════════════════════════════════════════════════════════════════
# COMPREHENSIVE REPORT — new endpoint
# ════════════════════════════════════════════════════════════════════════════

@login_required
def comprehensive_report_page(request):
    """
    Page that lets user pick a date range and download the full Excel report.
    GET  → render the form with a preview of today's key stats
    POST → redirect to the download
    """
    today = timezone.now().date()
    first_of_month = today.replace(day=1)

    if request.method == "POST":
        date_from = _parse_date(request.POST.get("date_from"), first_of_month)
        date_to   = _parse_date(request.POST.get("date_to"),   today)
        return redirect(
            f"{request.path}download/?date_from={date_from}&date_to={date_to}"
        )

    # Quick preview stats for the default period
    from .services_comprehensive import ComprehensiveReportService
    preview = None
    try:
        summary = ComprehensiveReportService._sales_summary(first_of_month, today)
        inv     = ComprehensiveReportService._inventory_data(first_of_month, today)
        preview = {
            "total_orders":     summary["total_orders"],
            "total_revenue":    summary["total_sales"],
            "total_customers":  summary["total_customers"],
            "products_tracked": inv["total_products"],
            "items_sold":       summary["total_items_sold"],
            "credit_sales":     summary["credit_sales"],
        }
    except Exception:
        pass

    return render(request, "reports/comprehensive_report.html", {
        "today":           today,
        "first_of_month":  first_of_month,
        "preview":         preview,
    })


@login_required
def comprehensive_report_download(request):
    """
    Stream the comprehensive Excel report for the requested date range.
    GET /reports/comprehensive/download/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
    """
    today = timezone.now().date()
    date_from = _parse_date(request.GET.get("date_from"), today.replace(day=1))
    date_to   = _parse_date(request.GET.get("date_to"),   today)

    if date_from > date_to:
        date_from, date_to = date_to, date_from

    try:
        from .services_comprehensive import ComprehensiveReportService
        excel_bytes = ComprehensiveReportService.generate_excel(date_from, date_to)

        filename = f"EJGlobal_Report_{date_from}_{date_to}.xlsx"
        response = HttpResponse(
            excel_bytes,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    except Exception as exc:
        messages.error(request, f"Report generation failed: {exc}")
        return redirect("reports:comprehensive_report")