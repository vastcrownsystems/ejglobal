from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os


font_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "fonts",
    "DejaVuSans.ttf"
)

pdfmetrics.registerFont(TTFont("DejaVuSans", font_path))


class InventoryMovementPDFExporter:

    def export(self, data, filepath):
        styles = getSampleStyleSheet()

        styles["Normal"].fontName = "DejaVuSans"
        styles["Title"].fontName = "DejaVuSans"

        styles.add(ParagraphStyle(
            name="CellLeft",
            parent=styles["Normal"],
            fontName="DejaVuSans",
            fontSize=8,
            leading=10,
            alignment=TA_LEFT,
        ))

        styles.add(ParagraphStyle(
            name="CellCenter",
            parent=styles["Normal"],
            fontName="DejaVuSans",
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
        ))

        styles.add(ParagraphStyle(
            name="HeaderCenter",
            parent=styles["Normal"],
            fontName="DejaVuSans",
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=white,
        ))

        doc = SimpleDocTemplate(
            filepath,
            pagesize=landscape(A4),
            leftMargin=18,
            rightMargin=18,
            topMargin=18,
            bottomMargin=18,
        )

        elements = []

        # ======================
        # TITLE BAR
        # ======================

        title_table = Table(
            [[Paragraph("<b>INVENTORY MOVEMENT REPORT</b>", styles["Title"])]],
            colWidths=[780]
        )

        title_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#0D47A1")),
            ("TEXTCOLOR", (0, 0), (-1, -1), white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))
        elements.append(title_table)

        elements.append(Spacer(1, 8))
        elements.append(
            Paragraph(f"Period: {data.get('date_range', '')}", styles["Normal"])
        )
        elements.append(Spacer(1, 16))

        # ======================
        # SUMMARY BOX
        # ======================

        summary = data.get("summary", {})

        summary_rows = [
            [
                Paragraph("<b>Total Movements</b>", styles["Normal"]),
                Paragraph(str(summary.get("total_movements", 0)), styles["CellCenter"]),
            ]
        ]

        summary_table = Table(summary_rows, colWidths=[220, 120])
        summary_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, black),
            ("BACKGROUND", (0, 0), (0, -1), HexColor("#F3F4F6")),
            ("FONTNAME", (0, 0), (-1, -1), "DejaVuSans"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))

        summary_wrap = Table([[summary_table]], colWidths=[780])
        summary_wrap.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ]))

        elements.append(summary_wrap)
        elements.append(Spacer(1, 18))

        # ======================
        # DETAIL TABLE
        # ======================

        rows = [[
            Paragraph("<b>Date</b>", styles["HeaderCenter"]),
            Paragraph("<b>Product</b>", styles["HeaderCenter"]),
            Paragraph("<b>Variant</b>", styles["HeaderCenter"]),
            Paragraph("<b>SKU</b>", styles["HeaderCenter"]),
            Paragraph("<b>Movement</b>", styles["HeaderCenter"]),
            Paragraph("<b>Qty</b>", styles["HeaderCenter"]),
            Paragraph("<b>Before</b>", styles["HeaderCenter"]),
            Paragraph("<b>After</b>", styles["HeaderCenter"]),
        ]]

        movements = data.get("movements", [])
        for m in movements:
            movement_label = str(m.get("movement_type", ""))

            rows.append([
                Paragraph(str(m.get("date", "")), styles["CellCenter"]),
                Paragraph(str(m.get("product_name", "")), styles["CellLeft"]),
                Paragraph(str(m.get("variant_name", "")), styles["CellCenter"]),
                Paragraph(str(m.get("sku", "")), styles["CellLeft"]),
                Paragraph(movement_label, styles["CellCenter"]),
                Paragraph(str(m.get("quantity", 0)), styles["CellCenter"]),
                Paragraph(str(m.get("stock_before", 0)), styles["CellCenter"]),
                Paragraph(str(m.get("stock_after", 0)), styles["CellCenter"]),
            ])

        table = Table(
            rows,
            colWidths=[
                95,   # date
                150,  # product
                65,   # variant
                145,  # sku
                95,   # movement
                45,   # qty
                70,   # before
                70,   # after
            ],
            repeatRows=1,
        )

        style = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0D47A1")),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans"),
            ("FONTNAME", (0, 1), (-1, -1), "DejaVuSans"),

            ("GRID", (0, 0), (-1, -1), 0.5, black),

            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (5, 1), (-1, -1), "CENTER"),

            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                white,
                HexColor("#F8FAFC"),
            ]),

            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ])

        # Highlight movement type column
        for i, m in enumerate(movements, start=1):
            movement_type = str(m.get("movement_type", "")).upper()

            if movement_type in {"SALE"}:
                style.add("BACKGROUND", (4, i), (4, i), HexColor("#FEE2E2"))
                style.add("TEXTCOLOR", (4, i), (4, i), HexColor("#991B1B"))
                style.add("FONTNAME", (4, i), (4, i), "DejaVuSans")
            elif movement_type in {"RESTOCK"}:
                style.add("BACKGROUND", (4, i), (4, i), HexColor("#D1FAE5"))
                style.add("TEXTCOLOR", (4, i), (4, i), HexColor("#065F46"))
                style.add("FONTNAME", (4, i), (4, i), "DejaVuSans")
            elif movement_type in {"ADJ", "CORRECTION"}:
                style.add("BACKGROUND", (4, i), (4, i), HexColor("#DBEAFE"))
                style.add("TEXTCOLOR", (4, i), (4, i), HexColor("#1D4ED8"))
                style.add("FONTNAME", (4, i), (4, i), "DejaVuSans")
            elif movement_type in {"DAMAGE"}:
                style.add("BACKGROUND", (4, i), (4, i), HexColor("#FFF3CD"))
                style.add("TEXTCOLOR", (4, i), (4, i), HexColor("#664D03"))
                style.add("FONTNAME", (4, i), (4, i), "DejaVuSans")

        table.setStyle(style)
        elements.append(table)

        doc.build(elements)