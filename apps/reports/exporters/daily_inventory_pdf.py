from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
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

class DailyInventoryPDFExporter:

    def export(self, data, filepath):

        styles = getSampleStyleSheet()
        styles["Normal"].fontName = "DejaVuSans"
        styles["Title"].fontName = "DejaVuSans"

        doc = SimpleDocTemplate(
            filepath,
            pagesize=landscape(A4),
            leftMargin=20,
            rightMargin=20,
            topMargin=20,
            bottomMargin=20,
        )

        elements = []

        # ======================
        # TITLE
        # ======================

        title = Table(
            [[Paragraph("<b>DAILY INVENTORY REPORT</b>", styles["Title"])]],
            colWidths=[770]
        )

        title.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), HexColor("#0D47A1")),
            ("TEXTCOLOR", (0,0), (-1,-1), white),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("TOPPADDING", (0,0), (-1,-1), 10),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ]))

        elements.append(title)

        elements.append(
            Paragraph(f"Period: {data.get('date_range','')}", styles["Normal"])
        )

        elements.append(Spacer(1, 20))

        # ======================
        # SUMMARY
        # ======================

        s = data.get("summary", {})

        summary_rows = [
            ["Total Products", s.get("total_products", 0)],
            ["Total Opening Stock", s.get("total_opening_stock", 0)],
            ["Total Stock Added", s.get("total_stock_added", 0)],
            ["Adjustments Increase", s.get("total_adjustments_increase", 0)],
            ["Adjustments Decrease", s.get("total_adjustments_decrease", 0)],
            ["Total Quantity Sold", s.get("total_quantity_sold", 0)],
            ["Expected Closing", s.get("total_expected_closing", 0)],
            ["Actual Closing", s.get("total_actual_closing", 0)],
            ["Total Variance", s.get("total_variance", 0)],
            ["Total Stock Value", f"₦{s.get('total_revenue',0):,.2f}"],
        ]

        summary_table = Table(summary_rows, colWidths=[250, 150])

        summary_table.setStyle(TableStyle([
            ("GRID",(0,0),(-1,-1),0.5,black),
            ("BACKGROUND",(0,0),(0,-1),HexColor("#F3F4F6")),
            ("FONTNAME",(0,0),(-1,-1),"DejaVuSans"),
            ("ALIGN",(1,0),(1,-1),"RIGHT"),
        ]))

        elements.append(summary_table)

        elements.append(Spacer(1, 25))

        # ======================
        # PRODUCT TABLE
        # ======================

        rows = [[
            "Product",
            "Var",
            "SKU",
            "Cat",
            "Open",
            "Add",
            "Adj+",
            "Adj-",
            "Sales",
            "Exp",
            "Act",
            "Var",
            "Value"
        ]]

        for p in data.get("products", []):

            rows.append([
                p["product_name"],
                p["variant_name"],
                p["sku"],
                p["category"],
                p["opening_stock"],
                p["additions"],
                p["adjustments_increase"],
                p["adjustments_decrease"],
                p["sales"],
                p["expected_closing"],
                p["actual_closing"],
                p["variance"],
                f"₦{p['stock_value']:,.2f}",
            ])

        # ======================
        # CRITICAL FIX: COLUMN WIDTHS
        # ======================

        table = Table(
            rows,
            colWidths=[
                120,  # product
                40,   # variant
                120,  # sku
                60,   # category
                45,   # opening
                45,   # added
                45,   # adj+
                45,   # adj-
                45,   # sales
                55,   # expected
                55,   # actual
                45,   # variance
                65    # value
            ],
            repeatRows=1
        )

        table.setStyle(TableStyle([

            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0D47A1")),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),

            ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans"),
            ("FONTNAME", (0, 1), (-1, -1), "DejaVuSans"),

            ("GRID", (0, 0), (-1, -1), 0.5, black),

            ("ALIGN", (4, 1), (-1, -1), "CENTER"),

            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                white,
                HexColor("#F8FAFC")
            ])

        ]))

        elements.append(table)

        doc.build(elements)