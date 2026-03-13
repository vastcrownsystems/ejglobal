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


class CustomerAnalysisPDFExporter:

    def export(self,data,filepath):

        styles = getSampleStyleSheet()
        styles["Normal"].fontName="DejaVuSans"
        styles["Title"].fontName="DejaVuSans"

        doc=SimpleDocTemplate(
            filepath,
            pagesize=landscape(A4),
            leftMargin=20,
            rightMargin=20,
            topMargin=20,
            bottomMargin=20
        )

        elements=[]

        title=Table(
            [[Paragraph("<b>CUSTOMER ANALYSIS REPORT</b>",styles["Title"])]],
            colWidths=[770]
        )

        title.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),HexColor("#0D47A1")),
            ("TEXTCOLOR",(0,0),(-1,-1),white),
            ("ALIGN",(0,0),(-1,-1),"CENTER"),
        ]))

        elements.append(title)

        elements.append(
            Paragraph(f"Period: {data['date_range']}",styles["Normal"])
        )

        elements.append(Spacer(1,20))

        s=data["summary"]

        summary_rows=[
            ["Total Customers",s["total_customers"]],
            ["Total Revenue",f"₦{s['total_revenue']:,.2f}"],
            ["Avg Customer Value",f"₦{s['avg_customer_value']:,.2f}"],
        ]

        summary_table=Table(summary_rows,colWidths=[200,160])

        summary_table.setStyle(TableStyle([
            ("GRID",(0,0),(-1,-1),0.5,black),
            ("BACKGROUND",(0,0),(0,-1),HexColor("#F3F4F6")),
            ("FONTNAME",(0,0),(-1,-1),"DejaVuSans"),
        ]))

        elements.append(summary_table)

        elements.append(Spacer(1,20))

        rows=[[
            "Customer","Phone","Orders","Items",
            "Total Spent","Avg Order","First Purchase","Last Purchase"
        ]]

        for c in data["customers"]:
            rows.append([
                Paragraph(str(c["customer"]), styles["Normal"]),
                Paragraph(str(c["phone"]), styles["Normal"]),
                c["orders"],
                c["items"],
                f"₦{c['revenue']:,.2f}",
                f"₦{c['avg_order']:,.2f}",
                Paragraph(str(c["first_purchase"])[:19], styles["Normal"]),
                Paragraph(str(c["last_purchase"])[:19], styles["Normal"]),
            ])

        table=Table(
            rows,
            colWidths=[170,120,50,60,90,90,95,95],
            repeatRows=1
        )

        table.setStyle(TableStyle([

            ("BACKGROUND",(0,0),(-1,0),HexColor("#0D47A1")),
            ("TEXTCOLOR",(0,0),(-1,0),white),

            ("FONTNAME",(0,0),(-1,0),"DejaVuSans"),
            ("FONTNAME",(0,1),(-1,-1),"DejaVuSans"),

            ("GRID",(0,0),(-1,-1),0.5,black),

            ("ALIGN",(2,1),(5,-1),"CENTER"),

            ("ROWBACKGROUNDS",(0,1),(-1,-1),[
                white,
                HexColor("#F8FAFC")
            ])

        ]))

        elements.append(table)

        doc.build(elements)