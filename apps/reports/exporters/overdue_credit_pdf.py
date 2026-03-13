from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os


font_path=os.path.join(
    os.path.dirname(__file__),
    "..","fonts","DejaVuSans.ttf"
)

pdfmetrics.registerFont(TTFont("DejaVuSans",font_path))


class OverdueCreditPDFExporter:

    def export(self,data,filepath):

        styles=getSampleStyleSheet()
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
            [[Paragraph("<b>OVERDUE CREDIT REPORT</b>",styles["Title"])]],
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

        rows=[[
            "Customer","Phone","Invoice",
            "Due Date","Days Overdue",
            "Outstanding","Status"
        ]]

        for r in data["rows"]:

            rows.append([
                Paragraph(str(r["customer"]),styles["Normal"]),
                Paragraph(str(r["phone"]),styles["Normal"]),
                Paragraph(str(r["invoice"]),styles["Normal"]),
                str(r["due_date"]),
                r["days_overdue"],
                f"₦{r['outstanding']:,.2f}",
                r["status"]
            ])

        table=Table(
            rows,
            colWidths=[200,130,120,90,90,110,80],
            repeatRows=1
        )

        table.setStyle(TableStyle([

            ("BACKGROUND",(0,0),(-1,0),HexColor("#0D47A1")),
            ("TEXTCOLOR",(0,0),(-1,0),white),

            ("FONTNAME",(0,0),(-1,0),"DejaVuSans"),
            ("FONTNAME",(0,1),(-1,-1),"DejaVuSans"),

            ("GRID",(0,0),(-1,-1),0.5,black),

            ("ALIGN",(4,1),(5,-1),"RIGHT"),

            ("ROWBACKGROUNDS",(0,1),(-1,-1),[
                white,
                HexColor("#F8FAFC")
            ])

        ]))

        elements.append(table)

        doc.build(elements)