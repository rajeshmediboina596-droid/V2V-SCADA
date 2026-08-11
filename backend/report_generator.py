from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import os
from backend.database import get_recent_incidents
from datetime import datetime

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'reports')

def generate_pdf_report():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    filename = f"incident_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(REPORTS_DIR, filename)
    
    doc = SimpleDocTemplate(filepath, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    story.append(Paragraph("V2V SCADA Dashboard - Session Incident Report", styles['Title']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 24))
    
    incidents = get_recent_incidents(100)
    
    if not incidents:
        story.append(Paragraph("No incidents recorded in this session.", styles['Normal']))
    else:
        # Table Header
        data = [["Time", "Vehicle A", "Vehicle B", "Dist (m)", "Closing Speed (m/s)", "Risk Level"]]
        
        for inc in incidents:
            # id, v_a, v_b, dist, speed, risk, time
            row = [
                str(inc[6]),
                str(inc[1]),
                str(inc[2]),
                f"{inc[3]:.2f}",
                f"{inc[4]:.2f}",
                str(inc[5])
            ]
            data.append(row)
            
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(table)
        
    doc.build(story)
    return filepath
