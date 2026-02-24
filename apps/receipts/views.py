# apps/receipts/views.py - Receipt Views with Modal Support

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from io import BytesIO
import logging

from .models import Receipt
from .services import ReceiptService

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET"])
def receipt_modal(request, pk):
    """
    Load receipt as modal for printing

    URL: GET /receipts/<pk>/modal/
    Returns: Receipt modal HTML
    """
    receipt = get_object_or_404(
        Receipt.objects.select_related(
            'order',
            'order__customer',
            'order__created_by'
        ).prefetch_related(
            'order__items',
            'order__order_payments'
        ),
        pk=pk
    )

    context = {
        'receipt': receipt,
    }

    return render(request, 'receipts/receipt_modal.html', context)


@login_required
@require_http_methods(["GET"])
def receipt_detail(request, pk):
    """
    View receipt detail page (full page view)

    URL: GET /receipts/<pk>/
    Returns: Receipt detail page
    """
    receipt = get_object_or_404(
        Receipt.objects.select_related(
            'order',
            'order__customer',
            'order__created_by'
        ).prefetch_related(
            'order__items',
            'order__order_payments'
        ),
        pk=pk
    )

    context = {
        'receipt': receipt,
    }

    return render(request, 'receipts/receipt_detail.html', context)


@login_required
@require_http_methods(["GET"])
def receipt_print(request, pk):
    """
    Print-optimized receipt view (80mm thermal)

    URL: GET /receipts/<pk>/print/
    Returns: Print-ready receipt HTML
    """
    receipt = get_object_or_404(
        Receipt.objects.select_related(
            'order',
            'order__customer',
            'order__created_by'
        ).prefetch_related(
            'order__items',
            'order__order_payments'
        ),
        pk=pk
    )

    context = {
        'receipt': receipt,
    }

    return render(request, 'receipts/receipt_print.html', context)


@login_required
@require_http_methods(["POST"])
def increment_print_count(request, pk):
    """
    Increment print count when receipt is printed

    URL: POST /receipts/<pk>/print-count/
    Returns: JSON response
    """
    try:
        receipt = get_object_or_404(Receipt, pk=pk)

        with transaction.atomic():
            receipt.print_count += 1
            receipt.save(update_fields=['print_count'])

        logger.info(f"Receipt {receipt.receipt_no} printed (count: {receipt.print_count})")

        return JsonResponse({
            'success': True,
            'print_count': receipt.print_count
        })

    except Exception as e:
        logger.exception(f"Error incrementing print count: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["GET"])
def download_pdf(request, pk):
    """
    Download receipt as PDF with full formatting.

    URL: GET /receipts/<pk>/download/
    Returns: PDF file (80mm-style layout on A4)
    """
    from apps.receipts.models import Receipt

    receipt = get_object_or_404(Receipt, pk=pk)

    try:
        # Generate PDF
        buffer = BytesIO()

        # Use A4 but center the 80mm-width content
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
        )

        story = []
        styles = getSampleStyleSheet()

        # ─── Custom Styles ───────────────────────────────────────────────

        # Company name (centered, bold)
        company_style = ParagraphStyle(
            'CompanyName',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#0033A0'),
            alignment=TA_CENTER,
            spaceAfter=4,
            fontName='Helvetica-Bold',
        )

        # Company info (centered, smaller)
        company_info_style = ParagraphStyle(
            'CompanyInfo',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            spaceAfter=2,
        )

        # Receipt title
        receipt_title_style = ParagraphStyle(
            'ReceiptTitle',
            parent=styles['Heading2'],
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=4,
            spaceBefore=8,
            fontName='Helvetica-Bold',
        )

        # Receipt number
        receipt_no_style = ParagraphStyle(
            'ReceiptNumber',
            parent=styles['Normal'],
            fontSize=12,
            alignment=TA_CENTER,
            fontName='Courier-Bold',
            spaceAfter=12,
        )

        # Section header
        section_header_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading3'],
            fontSize=11,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#0033A0'),
            spaceAfter=6,
            spaceBefore=10,
        )

        # ─── Header ──────────────────────────────────────────────────────

        story.append(Paragraph('EJ GLOBAL SERVICES', company_style))
        story.append(Paragraph('Your trusted partner', company_info_style))
        story.append(Paragraph('Tel: +234-XXX-XXX-XXXX', company_info_style))
        story.append(Paragraph('Email: info@ejglobal.com', company_info_style))

        story.append(Spacer(1, 8))
        story.append(Paragraph('SALES RECEIPT', receipt_title_style))
        story.append(Paragraph(receipt.receipt_no, receipt_no_style))

        # Horizontal line
        story.append(Spacer(1, 4))

        # ─── Transaction Info ────────────────────────────────────────────

        data = receipt.payload

        info_data = [
            ['Date:', receipt.created_at.strftime('%b %d, %Y %I:%M %p')],
            ['Order:', data['order']['order_number']],
            ['Cashier:', data['cashier']['name']],
        ]

        if data.get('session') and data['session'].get('register_name'):
            info_data.append(['Register:', data['session']['register_name']])

        info_table = Table(info_data, colWidths=[50 * mm, 100 * mm])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(info_table)

        # ─── Customer ────────────────────────────────────────────────────

        customer = data.get('customer', {})

        if not customer.get('is_walk_in', True):
            story.append(Spacer(1, 8))
            story.append(Paragraph('CUSTOMER', section_header_style))

            cust_data = [['Name:', customer.get('name', '')]]
            if customer.get('phone'):
                cust_data.append(['Phone:', customer['phone']])
            if customer.get('email'):
                cust_data.append(['Email:', customer['email']])
            if customer.get('customer_number'):
                cust_data.append(['Customer #:', customer['customer_number']])

            cust_table = Table(cust_data, colWidths=[50 * mm, 100 * mm])
            cust_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(cust_table)
        else:
            story.append(Spacer(1, 4))
            story.append(Paragraph('<b>Customer:</b> Walk-in Customer', styles['Normal']))

        # ─── Items ───────────────────────────────────────────────────────

        story.append(Spacer(1, 10))
        story.append(Paragraph('ITEMS', section_header_style))

        items_data = [['Item', 'Qty', 'Price', 'Total']]

        for item in data.get('items', []):
            items_data.append([
                Paragraph(item.get('display_name', ''), styles['Normal']),
                str(int(item.get('quantity', 0))),
                f"₦{item.get('unit_price', 0):.2f}",
                f"₦{item.get('line_total', 0):.2f}",
            ])

            # Show discount if any
            if item.get('discount_amount', 0) > 0:
                items_data.append([
                    Paragraph(f"<i>Discount</i>", styles['Normal']),
                    '',
                    '',
                    f"-₦{item['discount_amount']:.2f}",
                ])

        items_table = Table(items_data, colWidths=[80 * mm, 20 * mm, 25 * mm, 25 * mm])
        items_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F0F2F5')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),

            # Data rows
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 6),

            # Alignment
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),  # Qty center
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),  # Price/Total right

            # Grid
            ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#0033A0')),
            ('LINEBELOW', (0, 1), (-1, -2), 0.5, colors.HexColor('#E8E8E8')),
        ]))
        story.append(items_table)

        # ─── Totals ──────────────────────────────────────────────────────

        story.append(Spacer(1, 10))

        totals = data.get('totals', {})

        totals_data = [['Subtotal:', f"₦{totals.get('subtotal', 0):.2f}"]]

        if totals.get('discount_amount', 0) > 0:
            totals_data.append(['Discount:', f"-₦{totals['discount_amount']:.2f}"])

        if totals.get('tax_amount', 0) > 0:
            totals_data.append(['Tax:', f"₦{totals['tax_amount']:.2f}"])

        totals_table = Table(totals_data, colWidths=[100 * mm, 50 * mm])
        totals_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(totals_table)

        # Grand total
        grand_total_data = [['TOTAL:', f"₦{totals.get('total', 0):.2f}"]]
        grand_total_table = Table(grand_total_data, colWidths=[100 * mm, 50 * mm])
        grand_total_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#7FBA00')),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('LINEABOVE', (0, 0), (-1, 0), 2, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(grand_total_table)

        # ─── Payments ────────────────────────────────────────────────────

        story.append(Spacer(1, 10))
        story.append(Paragraph('PAYMENT', section_header_style))

        payment_data = []
        for payment in data.get('payments', []):
            payment_data.append([
                payment.get('payment_method_display', ''),
                f"₦{payment.get('amount', 0):.2f}",
            ])
            if payment.get('reference_number'):
                payment_data.append([
                    Paragraph(f"<i>Ref: {payment['reference_number']}</i>", styles['Normal']),
                    '',
                ])

        payment_data.append(['', ''])  # spacer
        payment_data.append([Paragraph('<b>Paid:</b>', styles['Normal']), f"₦{totals.get('paid_amount', 0):.2f}"])

        if totals.get('balance_due', 0) > 0:
            payment_data.append([Paragraph('<b>Balance:</b>', styles['Normal']), f"₦{totals['balance_due']:.2f}"])
        else:
            payment_data.append([Paragraph('<b>Change:</b>', styles['Normal']), '₦0.00'])

        payment_table = Table(payment_data, colWidths=[100 * mm, 50 * mm])
        payment_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LINEABOVE', (0, -2), (-1, -2), 1, colors.HexColor('#E8E8E8')),
        ]))
        story.append(payment_table)

        # ─── Footer ──────────────────────────────────────────────────────

        story.append(Spacer(1, 20))

        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
        )

        story.append(Paragraph('<b>THANK YOU!</b>', footer_style))
        story.append(Paragraph('Please come again', footer_style))
        story.append(Paragraph('Goods sold are not returnable', footer_style))

        story.append(Spacer(1, 10))
        story.append(Paragraph(f'<font name="Courier">{receipt.receipt_no}</font>', footer_style))

        if receipt.print_count > 0:
            story.append(Spacer(1, 4))
            story.append(Paragraph(f'<i>Reprint #{receipt.print_count}</i>', footer_style))

        # ─── Build PDF ───────────────────────────────────────────────────

        doc.build(story)

        # Return PDF
        pdf = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="receipt_{receipt.receipt_no}.pdf"'

        logger.info(f"PDF generated for receipt {receipt.receipt_no}")

        return response

    except Exception as e:
        logger.exception(f"Error generating PDF: {e}")
        return HttpResponse(f"Error generating PDF: {str(e)}", status=500)


@login_required
@require_http_methods(["GET"])
def receipt_list(request):
    """
    List all receipts

    URL: GET /receipts/
    Returns: Receipt list page
    """
    receipts = Receipt.objects.select_related(
        'order',
        'order__customer'
    ).order_by('-created_at')[:50]

    context = {
        'receipts': receipts,
    }

    return render(request, 'receipts/receipt_list.html', context)