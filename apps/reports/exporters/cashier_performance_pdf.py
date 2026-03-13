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


class CashierPerformancePDFExporter:

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

        # Header title
        title = Table(
            [[Paragraph("<b>CASHIER PERFORMANCE REPORT</b>", styles["Title"])]],
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

        # Summary
        s = data["summary"]

        summary_rows = [
            ["Total Cashiers", s["total_cashiers"]],
            ["Total Orders", s["total_orders"]],
            ["Total Revenue", f"₦{s['total_revenue']:,.2f}"],
            ["Total Sessions", s["total_sessions"]],
        ]

        summary_table = Table(summary_rows, colWidths=[200,150])

        summary_table.setStyle(TableStyle([
            ("GRID",(0,0),(-1,-1),0.5,black),
            ("BACKGROUND",(0,0),(0,-1),HexColor("#F3F4F6")),
            ("FONTNAME",(0,0),(-1,-1),"DejaVuSans"),
        ]))

        elements.append(summary_table)

        elements.append(Spacer(1,20))

        # Cashier performance table
        rows = [["Cashier","Orders","Items Sold","Revenue","Avg Order","First Sale","Last Sale"]]

        for c in data["cashiers"]:
            rows.append([
                c["cashier"],
                c["orders"],
                c["items_sold"],
                f"₦{c['revenue']:,.2f}",
                f"₦{c['avg_order']:,.2f}",
                str(c["first_sale"])[:19],
                str(c["last_sale"])[:19]
            ])

        table = Table(
            rows,
            colWidths=[180,70,90,120,120,120,120],
            repeatRows=1
        )

        table.setStyle(TableStyle([

            ("BACKGROUND",(0,0),(-1,0),HexColor("#0D47A1")),
            ("TEXTCOLOR",(0,0),(-1,0),white),

            ("FONTNAME",(0,0),(-1,0),"DejaVuSans"),
            ("FONTNAME",(0,1),(-1,-1),"DejaVuSans"),

            ("GRID",(0,0),(-1,-1),0.5,black),

            ("ALIGN",(1,1),(-1,-1),"CENTER"),

            ("ROWBACKGROUNDS",(0,1),(-1,-1),[
                white,
                HexColor("#F8FAFC")
            ])

        ]))

        elements.append(table)

        elements.append(Spacer(1,25))

        # Session analysis
        elements.append(
            Paragraph("<b>Session Analysis</b>", styles["Normal"])
        )

        elements.append(Spacer(1,10))

        rows = [["Session","Store","Register","Cashier","Opened","Closed","Orders","Revenue"]]

        for s in data["sessions"]:
            rows.append([
                s["session"],
                s["store"],
                s["register"],
                s["cashier"],
                str(s["opened"])[:19],
                str(s["closed"])[:19] if s["closed"] else "",
                s["orders"],
                f"₦{s['revenue']:,.2f}"
            ])

        table = Table(
            rows,
            colWidths=[60,120,120,120,120,120,70,100],
            repeatRows=1
        )

        table.setStyle(TableStyle([

            ("BACKGROUND",(0,0),(-1,0),HexColor("#0D47A1")),
            ("TEXTCOLOR",(0,0),(-1,0),white),

            ("FONTNAME",(0,0),(-1,0),"DejaVuSans"),
            ("FONTNAME",(0,1),(-1,-1),"DejaVuSans"),

            ("GRID",(0,0),(-1,-1),0.5,black),

            ("ALIGN",(6,1),(-1,-1),"CENTER"),

            ("ROWBACKGROUNDS",(0,1),(-1,-1),[
                white,
                HexColor("#F8FAFC")
            ])

        ]))

        elements.append(table)

        doc.build(elements)