"""
Генерация PDF отчёта по одной смене.
"""

import io
from datetime import datetime
from typing import Optional
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, Image,
)
from reportlab.lib.enums import TA_CENTER


def generate_shift_pdf(shift_info: dict, photo_before_bytes: Optional[bytes] = None,
                       photo_after_bytes: Optional[bytes] = None) -> bytes:
    """
    shift_info: {
        employee, role, object, address,
        started, ended, hours,
        start_lat, start_lon, end_lat, end_lon,
        installed, remaining, problems,
    }
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Title"],
        fontSize=18, spaceAfter=4, alignment=TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        "Sub", parent=styles["Normal"],
        fontSize=10, spaceAfter=10, alignment=TA_CENTER,
        textColor=colors.gray,
    )
    h2_style = ParagraphStyle(
        "H2", parent=styles["Heading2"],
        fontSize=12, spaceAfter=6, spaceBefore=8,
        textColor=colors.HexColor("#1A5276"),
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=10, spaceAfter=4,
    )

    story = []

    # Header
    story.append(Paragraph("FCS — Shift Report", title_style))
    story.append(Paragraph(
        f"{shift_info.get('started', 'N/A')}", subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1A5276")))
    story.append(Spacer(1, 0.3*cm))

    # Info table
    info_data = [
        ["Employee", shift_info.get("employee", "—")],
        ["Role", shift_info.get("role", "—")],
        ["Object", shift_info.get("object", "—")],
        ["Address", shift_info.get("address", "—")],
        ["Start time", shift_info.get("started", "—")],
        ["End time", shift_info.get("ended", "—")],
        ["Total hours", f"{shift_info.get('hours', 0):.2f}"],
    ]
    info_table = Table(info_data, colWidths=[4*cm, 12*cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EBF5FB")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D5D8DC")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.4*cm))

    # GPS table
    if shift_info.get("start_lat"):
        gps_data = [
            ["", "Latitude", "Longitude"],
            ["Start", f"{shift_info.get('start_lat', 0):.6f}", f"{shift_info.get('start_lon', 0):.6f}"],
            ["End", f"{shift_info.get('end_lat', 0):.6f}" if shift_info.get('end_lat') else "—",
                    f"{shift_info.get('end_lon', 0):.6f}" if shift_info.get('end_lon') else "—"],
        ]
        gps_table = Table(gps_data, colWidths=[3*cm, 6.5*cm, 6.5*cm])
        gps_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A5276")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D5D8DC")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(Paragraph("GPS coordinates", h2_style))
        story.append(gps_table)
        story.append(Spacer(1, 0.4*cm))

    # Punch List
    has_punch = any([
        shift_info.get("installed"),
        shift_info.get("remaining"),
        shift_info.get("problems"),
    ])
    if has_punch:
        story.append(Paragraph("Work Report", h2_style))
        if shift_info.get("installed"):
            story.append(Paragraph(f"<b>Installed:</b> {shift_info['installed']}", body_style))
        if shift_info.get("remaining"):
            story.append(Paragraph(f"<b>Remaining:</b> {shift_info['remaining']}", body_style))
        if shift_info.get("problems"):
            story.append(Paragraph(f"<b>Problems:</b> {shift_info['problems']}", body_style))
        story.append(Spacer(1, 0.4*cm))

    # Photos
    photos_added = False
    if photo_before_bytes:
        try:
            story.append(Paragraph("Photo BEFORE", h2_style))
            img = Image(io.BytesIO(photo_before_bytes), width=15*cm, height=11*cm, kind="proportional")
            story.append(img)
            story.append(Spacer(1, 0.3*cm))
            photos_added = True
        except Exception:
            pass

    if photo_after_bytes:
        try:
            story.append(Paragraph("Photo AFTER", h2_style))
            img = Image(io.BytesIO(photo_after_bytes), width=15*cm, height=11*cm, kind="proportional")
            story.append(img)
            photos_added = True
        except Exception:
            pass

    # Footer
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.gray))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%d.%m.%Y %H:%M')} | FCS Bot",
        ParagraphStyle("footer", parent=styles["Normal"], fontSize=8,
                       textColor=colors.gray, alignment=TA_CENTER)
    ))

    doc.build(story)
    return buffer.getvalue()
