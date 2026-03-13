from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from reportlab.lib.colors import HexColor


class LowStockPDFExporter:
    """
    Professional Low Stock PDF Exporter
    Styled to feel closer to the Excel design.
    """

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._build_styles()

    def _build_styles(self):
        self.styles.add(ParagraphStyle(
            name="LowStockTitle",
            parent=self.styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=colors.white,
            alignment=TA_CENTER,
            spaceAfter=0,
            leading=18,
        ))

        self.styles.add(ParagraphStyle(
            name="LowStockSubTitle",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=colors.black,
            alignment=TA_CENTER,
            spaceAfter=0,
        ))

        self.styles.add(ParagraphStyle(
            name="SummaryLabel",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=colors.black,
            alignment=TA_LEFT,
        ))

        self.styles.add(ParagraphStyle(
            name="SummaryValue",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.black,
            alignment=TA_LEFT,
        ))

        self.styles.add(ParagraphStyle(
            name="CellText",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.black,
            alignment=TA_LEFT,
        ))

        self.styles.add(ParagraphStyle(
            name="CellTextCenter",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.black,
            alignment=TA_CENTER,
        ))

    def export(self, data, filepath):
        doc = SimpleDocTemplate(
            filepath,
            pagesize=landscape(A4),
            leftMargin=0.4 * inch,
            rightMargin=0.4 * inch,
            topMargin=0.35 * inch,
            bottomMargin=0.35 * inch,
        )

        elements = []

        # ===== Title band =====
        title_table = Table(
            [[Paragraph("LOW STOCK ALERT REPORT", self.styles["LowStockTitle"])]],
            colWidths=[10.8 * inch],
        )
        title_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#0D47A1")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(title_table)

        period_text = f"Period: {data.get('date_range', '')}"
        period_para = Paragraph(period_text, self.styles["LowStockSubTitle"])
        elements.append(Spacer(1, 0.08 * inch))
        elements.append(period_para)
        elements.append(Spacer(1, 0.18 * inch))

        # ===== Summary box =====
        summary = data.get("summary", {})
        summary_data = [
            [
                Paragraph("Total Products", self.styles["SummaryLabel"]),
                Paragraph(str(summary.get("total_products", 0)), self.styles["SummaryValue"]),
            ],
            [
                Paragraph("Low Stock Items", self.styles["SummaryLabel"]),
                Paragraph(str(summary.get("low_stock_items", 0)), self.styles["SummaryValue"]),
            ],
            [
                Paragraph("Out of Stock", self.styles["SummaryLabel"]),
                Paragraph(str(summary.get("out_of_stock", 0)), self.styles["SummaryValue"]),
            ],
            [
                Paragraph("Critical Level", self.styles["SummaryLabel"]),
                Paragraph(str(summary.get("critical", 0)), self.styles["SummaryValue"]),
            ],
        ]

        summary_table = Table(summary_data, colWidths=[2.3 * inch, 1.6 * inch])
        summary_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.6, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), HexColor("#F3F4F6")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))

        summary_wrap = Table([[summary_table]], colWidths=[10.8 * inch])
        summary_wrap.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        elements.append(summary_wrap)
        elements.append(Spacer(1, 0.22 * inch))

        # ===== Main detail table =====
        rows = [[
            Paragraph("Product Name", self.styles["CellTextCenter"]),
            Paragraph("Variant", self.styles["CellTextCenter"]),
            Paragraph("SKU", self.styles["CellTextCenter"]),
            Paragraph("Category", self.styles["CellTextCenter"]),
            Paragraph("Current Stock", self.styles["CellTextCenter"]),
            Paragraph("Reorder Level", self.styles["CellTextCenter"]),
            Paragraph("Shortage", self.styles["CellTextCenter"]),
            Paragraph("Status", self.styles["CellTextCenter"]),
        ]]

        products = data.get("products", [])
        for item in products:
            rows.append([
                Paragraph(str(item.get("product_name", "")), self.styles["CellText"]),
                Paragraph(str(item.get("variant_name", "")), self.styles["CellTextCenter"]),
                Paragraph(str(item.get("sku", "")), self.styles["CellText"]),
                Paragraph(str(item.get("category", "")), self.styles["CellTextCenter"]),
                Paragraph(str(item.get("stock_quantity", 0)), self.styles["CellTextCenter"]),
                Paragraph(str(item.get("reorder_level", 0)), self.styles["CellTextCenter"]),
                Paragraph(str(item.get("difference", 0)), self.styles["CellTextCenter"]),
                Paragraph(str(item.get("status", "")), self.styles["CellTextCenter"]),
            ])

        # Total usable width ~ 10.8in
        col_widths = [
            2.0 * inch,   # product
            0.9 * inch,   # variant
            2.1 * inch,   # sku
            1.0 * inch,   # category
            0.9 * inch,   # current
            0.95 * inch,  # reorder
            0.75 * inch,  # shortage
            1.2 * inch,   # status
        ]

        detail_table = Table(rows, colWidths=col_widths, repeatRows=1)
        detail_style = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0D47A1")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),

            ("ROWBACKGROUNDS", (0, 1), (-2, -1), [
                colors.white,
                HexColor("#F9FAFB"),
            ]),

            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ])

        # Status coloring
        for idx, item in enumerate(products, start=1):
            status = str(item.get("status", "")).upper()

            if status == "OUT OF STOCK":
                detail_style.add("BACKGROUND", (7, idx), (7, idx), HexColor("#F8D7DA"))
                detail_style.add("TEXTCOLOR", (7, idx), (7, idx), HexColor("#842029"))
                detail_style.add("FONTNAME", (7, idx), (7, idx), "Helvetica-Bold")
            elif status == "CRITICAL":
                detail_style.add("BACKGROUND", (7, idx), (7, idx), HexColor("#FFE5B4"))
                detail_style.add("TEXTCOLOR", (7, idx), (7, idx), HexColor("#8A4B08"))
                detail_style.add("FONTNAME", (7, idx), (7, idx), "Helvetica-Bold")
            elif status == "LOW":
                detail_style.add("BACKGROUND", (7, idx), (7, idx), HexColor("#FFF3CD"))
                detail_style.add("TEXTCOLOR", (7, idx), (7, idx), HexColor("#664D03"))
                detail_style.add("FONTNAME", (7, idx), (7, idx), "Helvetica-Bold")

        detail_table.setStyle(detail_style)
        elements.append(detail_table)

        doc.build(elements)