from django.shortcuts import render, get_object_or_404, redirect
from django.http import FileResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.utils import timezone

from .models import ReportTemplate, GeneratedReport
from .services import ReportService


@login_required
def reports_dashboard(request):
    """
    Reports dashboard
    """

    context = ReportService.build_dashboard_context(request.user)

    return render(
        request,
        "reports/reports_dashboard.html",
        context
    )


@login_required
def generate_report(request, report_type):
    """
    Generate report
    """

    template = get_object_or_404(
        ReportTemplate,
        report_type=report_type,
        is_active=True
    )

    if request.method == "POST":

        date_from = request.POST.get("date_from")
        date_to = request.POST.get("date_to")
        file_format = request.POST.get("format", "EXCEL")

        report = ReportService.generate_report(
            report_template=template,
            generated_by=request.user,
            date_from=date_from,
            date_to=date_to,
            file_format=file_format
        )

        return redirect(
            "reports:download_report",
            pk=report.pk
        )

    context = {
        "template": template,
        "default_from": timezone.now().date(),
        "default_to": timezone.now().date(),
    }

    return render(
        request,
        "reports/generate_form.html",
        context
    )


@login_required
def download_report(request, pk):
    """
    Download generated report
    """

    report = get_object_or_404(
        GeneratedReport,
        pk=pk
    )

    if not report.file_path:
        return redirect("reports:dashboard")

    return FileResponse(
        report.file_path.open("rb"),
        as_attachment=True,
        filename=report.file_path.name.split("/")[-1]
    )


@login_required
def report_history(request):
    """
    Report history page
    """

    reports = GeneratedReport.objects.select_related(
        "report_template"
    ).order_by("-generated_at")

    paginator = Paginator(reports, 20)

    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "reports": page_obj,
        "page_obj": page_obj
    }

    return render(
        request,
        "reports/history.html",
        context
    )


@login_required
def quick_reports_api(request):
    """
    API for dashboard quick stats
    """

    today = timezone.now().date()

    data = {
        "today_sales": ReportService.get_sales_analytics(today, today),
        "inventory": ReportService.get_inventory_summary(today),
        "best_sellers": ReportService.get_best_sellers(today)
    }

    return JsonResponse(data)