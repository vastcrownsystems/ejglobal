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


class CreditAgingPDFExporter:

    def export(self,data,filepath):

        styles=getSampleStyleSheet()
        styles["Normal"].fontName="DejaVuSans"
        styles["Title"].fontName="DejaVuSans"
        styles["Normal"].wordWrap = "CJK"

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
            [[Paragraph("<b>CREDIT AGING REPORT</b>",styles["Title"])]],
            colWidths=[770]
        )

        title.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),HexColor("#0D47A1")),
            ("TEXTCOLOR",(0,0),(-1,-1),white),
            ("ALIGN",(0,0),(-1,-1),"CENTER"),
        ]))

        elements.append(title)

        elements.append(
            Paragraph(data["date_range"],styles["Normal"])
        )

        elements.append(Spacer(1,20))

        rows = [[
            Paragraph("Customer", styles["Normal"]),
            Paragraph("Phone", styles["Normal"]),
            Paragraph("Current", styles["Normal"]),
            Paragraph("1-30", styles["Normal"]),
            Paragraph("31-60", styles["Normal"]),
            Paragraph("61-90", styles["Normal"]),
            Paragraph("90+", styles["Normal"]),
            Paragraph("Total", styles["Normal"]),
        ]]

        for c in data["customers"]:
            rows.append([
                Paragraph(str(c["customer"]), styles["Normal"]),
                Paragraph(str(c["phone"]), styles["Normal"]),
                Paragraph(f"₦{c['current']:,.2f}", styles["Normal"]),
                Paragraph(f"₦{c['days_30']:,.2f}", styles["Normal"]),
                Paragraph(f"₦{c['days_60']:,.2f}", styles["Normal"]),
                Paragraph(f"₦{c['days_90']:,.2f}", styles["Normal"]),
                Paragraph(f"₦{c['days_120']:,.2f}", styles["Normal"]),
                Paragraph(f"₦{c['total']:,.2f}", styles["Normal"]),
            ])

        table=Table(
            rows,
            colWidths=[180,120,80,80,80,80,80,90],
            repeatRows=1
        )

        table.setStyle(TableStyle([

            ("BACKGROUND",(0,0),(-1,0),HexColor("#0D47A1")),
            ("TEXTCOLOR",(0,0),(-1,0),white),

            ("FONTNAME",(0,0),(-1,0),"DejaVuSans"),
            ("FONTNAME",(0,1),(-1,-1),"DejaVuSans"),

            ("GRID",(0,0),(-1,-1),0.5,black),

            ("ALIGN",(2,1),(-1,-1),"RIGHT"),

            ("ROWBACKGROUNDS",(0,1),(-1,-1),[
                white,
                HexColor("#F8FAFC")
            ])

        ]))

        elements.append(table)

        doc.build(elements)