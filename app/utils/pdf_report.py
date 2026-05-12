"""
Генерация PDF отчёта за день.
Использует reportlab.
"""

import io
from datetime import date
from typing import List
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def generate_daily_report(report_date: date, shifts_data: List[dict]) -> bytes:
    """
    shifts_data: список словарей с ключами:
      employee, object, start, end, hours, photos_before, photos_after, notes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Title"],
        fontSize=16, spaceAfter=6, alignment=TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        "Sub", parent=styles["Normal"],
        fontSize=11, spaceAfter=12, alignment=TA_CENTER,
        textColor=colors.gray,
    )
    label_style = ParagraphStyle(
        "Label", parent=styles["Normal"],
        fontSize=9, textColor=colors.gray,
    )
    value_style = ParagraphStyle(
        "Value", parent=styles["Normal"],
        fontSize=10,
    )

    story = []

    # Header
    story.append(Paragraph("FCS — Florida Cabinet Studio", title_style))
    story.append(Paragraph(f"Daily Report {report_date.strftime('%d.%m.%Y')}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1A5276")))
    story.append(Spacer(1, 0.4*cm))

    if not shifts_data:
        story.append(Paragraph("No shifts found for this day.", value_style))
    else:
        # Summary table
        total_hours = sum(float(s.get("hours") or 0) for s in shifts_data)
        summary_data = [
            ["Total Shifts", "Total Hours", "Employees"],
            [str(len(shifts_data)), f"{total_hours:.1f} ч.", str(len({s["employee"] for s in shifts_data}))],
        ]
        summary_table = Table(summary_data, colWidths=[5.5*cm, 5.5*cm, 5.5*cm])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1A5276")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTSIZE", (0,0), (-1,0), 10),
            ("FONTSIZE", (0,1), (-1,1), 12),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0,1), (-1,1), [colors.HexColor("#EBF5FB")]),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#D5D8DC")),
            ("TOPPADDING", (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.5*cm))

        # Detail table
        headers = ["Employee", "Object", "Start", "End", "Hours", "Photo Before", "Photo After"]
        table_data = [headers]
        for s in shifts_data:
            table_data.append([
                s.get("employee", "—"),
                s.get("object", "—"),
                s.get("start", "—"),
                s.get("end", "—"),
                f"{float(s.get('hours') or 0):.1f}",
                "✅" if s.get("photos_before") else "—",
                "✅" if s.get("photos_after") else "—",
            ])

        col_widths = [3.5*cm, 4*cm, 2*cm, 2*cm, 1.5*cm, 1.8*cm, 1.8*cm]
        detail_table = Table(table_data, colWidths=col_widths)
        detail_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2C3E50")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTSIZE", (0,0), (-1,0), 9),
            ("FONTSIZE", (0,1), (-1,-1), 9),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F8F9FA")]),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#D5D8DC")),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(detail_table)

        # Notes
        has_notes = any(s.get("notes") for s in shifts_data)
        if has_notes:
            story.append(Spacer(1, 0.5*cm))
            story.append(Paragraph("Notes:", ParagraphStyle("h", parent=styles["Heading3"], fontSize=11)))
            for s in shifts_data:
                if s.get("notes"):
                    story.append(Paragraph(
                        f"<b>{s['employee']}</b>: {s['notes']}",
                        value_style
                    ))

    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.gray))
    story.append(Paragraph(
        f"Generated: {date.today().strftime('%d.%m.%Y')} | FCS Bot",
        ParagraphStyle("footer", parent=styles["Normal"], fontSize=8,
                       textColor=colors.gray, alignment=TA_CENTER)
    ))

    doc.build(story)
    return buffer.getvalue()
