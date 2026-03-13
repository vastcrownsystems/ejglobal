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


class SalesSummaryPDFExporter:

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
            bottomMargin=20
        )

        elements = []

        title = Table(
            [[Paragraph("<b>SALES SUMMARY REPORT</b>", styles["Title"])]],
            colWidths=[770]
        )

        title.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),HexColor("#0D47A1")),
            ("TEXTCOLOR",(0,0),(-1,-1),white),
            ("ALIGN",(0,0),(-1,-1),"CENTER"),
        ]))

        elements.append(title)

        elements.append(
            Paragraph(f"Period: {data.get('date_range','')}", styles["Normal"])
        )

        elements.append(Spacer(1,20))

        s = data["summary"]

        summary_rows = [

            ["Total Orders", s["total_orders"]],
            ["Total Items Sold", s["total_items"]],
            ["Total Revenue", f"₦{s['total_revenue']:,.2f}"],

            ["", ""],

            ["Cash Sales", f"₦{s['cash_sales']:,.2f}"],
            ["Card Sales", f"₦{s['card_sales']:,.2f}"],
            ["Transfer Sales", f"₦{s['transfer_sales']:,.2f}"],
            ["Credit Sales", f"₦{s['credit_sales']:,.2f}"],

            ["", ""],

            ["Total Paid", f"₦{s['total_paid']:,.2f}"],
            ["Credit Sold", f"₦{s['credit_sold']:,.2f}"],

        ]

        summary_table = Table(summary_rows, colWidths=[200,150])

        summary_table.setStyle(TableStyle([
            ("GRID",(0,0),(-1,-1),0.5,black),
            ("BACKGROUND",(0,0),(0,-1),HexColor("#F3F4F6")),
            ("FONTNAME",(0,0),(-1,-1),"DejaVuSans"),
        ]))

        elements.append(summary_table)

        elements.append(Spacer(1,20))

        rows = [["Product","Variant","SKU","Qty","Unit Price","Revenue"]]

        for p in data["products"]:

            rows.append([
                p["product_name"],
                p["variant_name"],
                p["sku"],
                p["quantity_sold"],
                f"₦{p['unit_price']:,.2f}",
                f"₦{p['revenue']:,.2f}"
            ])

        table = Table(
            rows,
            colWidths=[220,80,200,60,100,110],
            repeatRows=1
        )

        table.setStyle(TableStyle([

            ("BACKGROUND",(0,0),(-1,0),HexColor("#0D47A1")),
            ("TEXTCOLOR",(0,0),(-1,0),white),

            ("FONTNAME",(0,0),(-1,0),"DejaVuSans"),
            ("FONTNAME",(0,1),(-1,-1),"DejaVuSans"),

            ("GRID",(0,0),(-1,-1),0.5,black),

            ("ALIGN",(3,1),(-1,-1),"CENTER"),

            ("ROWBACKGROUNDS",(0,1),(-1,-1),[
                white,
                HexColor("#F8FAFC")
            ])

        ]))

        elements.append(table)

        elements.append(Spacer(1, 25))

        # -------------------------
        # DAILY SALES TREND
        # -------------------------

        elements.append(
            Paragraph("<b>Daily Sales Trend</b>", styles["Normal"])
        )

        elements.append(Spacer(1, 10))

        trend_rows = [["Date", "Orders", "Revenue"]]

        for t in data.get("trend", []):
            trend_rows.append([
                str(t["date"]),
                t["orders"],
                f"₦{t['revenue']:,.2f}"
            ])

        trend_table = Table(
            trend_rows,
            colWidths=[200, 120, 160],
            repeatRows=1
        )

        trend_table.setStyle(TableStyle([

            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0D47A1")),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),

            ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans"),
            ("FONTNAME", (0, 1), (-1, -1), "DejaVuSans"),

            ("GRID", (0, 0), (-1, -1), 0.5, black),

            ("ALIGN", (1, 1), (-1, -1), "CENTER"),

            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                white,
                HexColor("#F8FAFC")
            ])

        ]))

        elements.append(trend_table)

        doc.build(elements)