from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import os
from datetime import datetime
from backend.database import get_recent_incidents
from backend.config import REPORTS_DIR

def generate_pdf_report():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    filename = f"incident_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(REPORTS_DIR, filename)

    doc = SimpleDocTemplate(filepath, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    story.append(Paragraph("V2V SCADA Dashboard - Vehicular Safety Incident Audit", styles['Title']))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Architecture: STM32 ARM Cortex-M | 2.4GHz RF | AIS-230 Compliance", styles['Normal']))
    story.append(Paragraph(f"Report Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 18))

    incidents = get_recent_incidents(100)

    def _safe_float(val, default=0.0):
        if val is None or val == '':
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    if not incidents:
        story.append(Paragraph("System Healthy — No collision hazards or safety violations recorded in this operational window.", styles['Normal']))
    else:
        # Table Header
        data = [["Time", "Vehicle A", "Vehicle B", "Dist (m)", "Closing (m/s)", "Risk", "TTC (s)"]]

        for inc in incidents:
            if isinstance(inc, dict):
                t_str = str(inc.get('incident_time', ''))
                va = str(inc.get('vehicle_a', ''))
                vb = str(inc.get('vehicle_b', ''))
                dist = f"{_safe_float(inc.get('distance')):.1f}"
                speed = f"{_safe_float(inc.get('closing_speed')):.1f}"
                risk = str(inc.get('risk_level', ''))
                ttc = f"{_safe_float(inc.get('ttc_seconds')):.1f}"
            else:
                t_str = str(inc[6]) if len(inc) > 6 else ""
                va = str(inc[1])
                vb = str(inc[2])
                dist = f"{_safe_float(inc[3] if len(inc) > 3 else 0.0):.1f}"
                speed = f"{_safe_float(inc[4] if len(inc) > 4 else 0.0):.1f}"
                risk = str(inc[5] if len(inc) > 5 else "")
                ttc = f"{_safe_float(inc[7]):.1f}" if len(inc) > 7 and inc[7] is not None else "N/A"

            data.append([t_str, va, vb, dist, speed, risk, ttc])

        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ]))
        story.append(table)

    doc.build(story)
    return filepath
