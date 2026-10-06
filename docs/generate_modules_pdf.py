"""Generate Modules & Functionalities PDF for project approval submission."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
import os

def build_pdf():
    doc = SimpleDocTemplate(
        "docs/Modules_and_Functionalities.pdf",
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=20*mm, bottomMargin=20*mm
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle('Title2', parent=styles['Title'],
        fontName='Times-Bold', fontSize=16, leading=20,
        spaceAfter=4, alignment=TA_CENTER)

    subtitle_style = ParagraphStyle('Sub', parent=styles['Normal'],
        fontName='Times-Bold', fontSize=13, leading=16,
        spaceAfter=4, alignment=TA_CENTER)

    project_title_style = ParagraphStyle('ProjTitle', parent=styles['Normal'],
        fontName='Times-Bold', fontSize=13, leading=17,
        spaceAfter=12, alignment=TA_CENTER)

    heading_style = ParagraphStyle('H2', parent=styles['Normal'],
        fontName='Times-Bold', fontSize=12, leading=15,
        spaceBefore=14, spaceAfter=8, backColor=colors.Color(0.91, 0.91, 0.91),
        borderPadding=(4, 6, 4, 6))

    normal = ParagraphStyle('Body', parent=styles['Normal'],
        fontName='Times-Roman', fontSize=11, leading=14, alignment=TA_JUSTIFY)

    bold = ParagraphStyle('Bold', parent=normal, fontName='Times-Bold')

    bullet = ParagraphStyle('Bullet', parent=normal,
        fontName='Times-Roman', fontSize=10.5, leading=13.5,
        leftIndent=12, bulletIndent=0, spaceBefore=1, spaceAfter=1)

    meta_label = ParagraphStyle('MetaL', parent=normal,
        fontName='Times-Bold', fontSize=11)
    meta_val = ParagraphStyle('MetaV', parent=normal,
        fontName='Times-Roman', fontSize=11)

    elements = []

    # ── Title Block ──
    elements.append(Paragraph("MODULES AND FUNCTIONALITIES", title_style))
    elements.append(Spacer(1, 2*mm))
    elements.append(Paragraph("Project Documentation for Guide Approval", subtitle_style))
    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph(
        "Real-Time Vehicle-to-Vehicle (V2V) Communication &amp;<br/>SCADA-Based Safety Monitoring System",
        project_title_style))

    # ── V2V Image ──
    img_path = "docs/v2v_cars.jpg"
    if os.path.exists(img_path):
        try:
            # Add the image, scaled to fit the page width reasonably
            img = Image(img_path, width=120*mm, height=70*mm)
            elements.append(img)
            elements.append(Spacer(1, 6*mm))
        except Exception as e:
            print(f"Could not load image {img_path}: {e}")

    # ── Meta Info ──
    meta_data = [
        ["Domain:", "Internet of Things (IoT) / Embedded Systems / Cyber-Physical Systems"],
        ["Technology Stack:", "STM32, SX1281, Python (FastAPI), MQTT, WebSockets, Scikit-Learn, HTML/CSS/JS, Leaflet.js"],
        ["Database:", "SQLite"],
        ["Communication:", "SX1281 2.4GHz LoRa/FLRC (Peer-to-Peer) / MQTT Protocol (Eclipse Mosquitto)"],
    ]
    meta_table = Table(meta_data, colWidths=[40*mm, 130*mm])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Times-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Times-Roman'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 4*mm))

    # ── Abstract ──
    elements.append(Paragraph("Abstract", heading_style))
    abstract_text = (
        "Road traffic accidents remain one of the leading causes of fatalities worldwide, "
        "with a significant proportion attributed to delayed collision warnings, limited driver visibility, "
        "and the absence of real-time inter-vehicle communication. Existing vehicular safety systems rely heavily on "
        "cloud-based infrastructure and cellular connectivity, rendering them ineffective in rural areas, tunnels, "
        "underground parking structures, and regions with poor network coverage. "
        "Recognizing this critical gap, the Government of India, through the Ministry of Road Transport and Highways (MoRTH), "
        "has introduced the <b>AIS-230 (Automotive Industry Standard 230)</b> mandate for Vehicle-to-Vehicle (V2V) communication. "
        "Effective <b>October 1, 2027</b>, all new vehicles equipped with V2V systems must voluntarily comply with AIS-230 standards. "
        "From <b>October 1, 2028</b>, it becomes <b>mandatory</b> for all newly manufactured cars, two-wheelers, three-wheelers, "
        "and commercial vehicles to incorporate AIS-230 compliant V2V communication technology based on C-V2X "
        "(Cellular Vehicle-to-Everything) operating on the 5.9 GHz band (5.875\u20135.925 GHz), enabling 360-degree "
        "non-line-of-sight hazard detection, real-time broadcasting of speed, braking status, position, and directional vectors, "
        "and integration with existing ADAS (Advanced Driver Assistance Systems) infrastructure."
        "<br/><br/>"
        "Aligned with this national regulatory direction, this project presents the design and implementation of a real-time, "
        "internet-independent V2V communication and SCADA (Supervisory Control and Data Acquisition) safety monitoring system. "
        "The proposed system employs STM32 Bluepill microcontrollers interfaced with GNSS (GPS) modules to acquire high-frequency "
        "telemetry data at 10 Hz, which is cryptographically signed using HMAC-SHA256 to ensure data integrity and "
        "prevent cyber-attacks such as Ghost Vehicle Injection and Man-in-the-Middle spoofing. "
        "The signed telemetry is transmitted via the MQTT protocol to a locally hosted backend built on "
        "Python FastAPI, which performs real-time collision risk assessment using the Haversine distance formula "
        "and a pre-trained Random Forest machine learning classifier. "
        "A full-screen SCADA HUD (Heads-Up Display) dashboard, developed using HTML5, CSS3, JavaScript, and Leaflet.js, "
        "provides operators with live vehicle tracking on an interactive map, predictive trajectory visualization, "
        "geofence breach detection, emergency vehicle priority alerting, deep packet inspection, and automated PDF report generation. "
        "The entire system operates on a local network without any internet dependency, making it suitable for deployment "
        "in closed environments such as mining sites, construction zones, port yards, and military convoys, "
        "as well as serving as a prototype reference implementation for the upcoming AIS-230 compliance framework. "
        "Experimental results demonstrate that the system successfully tracks up to 15 concurrent vehicles with an average "
        "end-to-end latency of under 30 milliseconds, validates cryptographic signatures in microseconds, and "
        "predicts collision risks with a 5-second advance warning window."
    )
    elements.append(Paragraph(abstract_text, normal))
    elements.append(Spacer(1, 4*mm))

    # ── Team Details ──
    elements.append(Paragraph("Team Members", heading_style))

    team_data = [
        ["S.No", "Student Name", "Roll Number"],
        ["1", "MEDIBOINA RAJESH", "NEC0824065"],
        ["2", "MADIREDDY CHENNA KESAVA REDDY", "NEC0824080"],
        ["3", "T MANJUNATH", "NEC0824051"],
        ["4", "THILAK RAJ", "NEC0824061"],
        ["5", "LAKSHMIPATHI T", "NEC0823087"],
    ]
    team_table = Table(team_data, colWidths=[15*mm, 85*mm, 70*mm])
    team_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Times-Roman'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.85, 0.85, 0.85)),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('ROWHEIGHT', (0, 1), (-1, -1), 22),
    ]))
    elements.append(team_table)
    elements.append(Spacer(1, 4*mm))

    # ── Modules Table ──
    elements.append(Paragraph("System Modules and Functionalities", heading_style))

    modules = [
        ("1", "IoT Firmware Module\n(STM32 Bluepill)", [
            "Acquires real-time GPS coordinates (Latitude, Longitude, Speed) from NEO-6M GNSS module via UART at 10 Hz.",
            "Constructs a JSON telemetry payload with Vehicle ID, Type, Timestamp, GPS data, and Heading.",
            "Generates an HMAC-SHA256 cryptographic signature for each payload to prevent data tampering.",
            "Broadcasts telemetry over 2.4GHz using SX1281 RF transceivers for long-range peer-to-peer data mesh.",
            "Provides 360-degree Non-Line-of-Sight (NLOS) coverage to detect hazards around sharp curves and large vehicles.",
            "Subscribes to v2v/alerts and v2v/commands to receive collision warnings and broadcast commands from the backend.",
        ]),
        ("2", "MQTT Communication Module\n(Eclipse Mosquitto)", [
            "Acts as the central message broker running on localhost (port 1883) for all publish/subscribe communication.",
            "Manages topic-based routing: v2v/telemetry (vehicles to backend), v2v/alerts (backend to vehicles), v2v/commands (backend to all).",
            "Supports TLS encryption on port 8883 using generated certificates for secure transport.",
            "Operates entirely on the local network with no internet or cloud dependency.",
        ]),
        ("3", "Security & Authentication Module\n(Backend — Python)", [
            "Verifies the HMAC-SHA256 signature of every incoming telemetry packet using constant-time comparison (hmac.compare_digest) to prevent timing attacks.",
            "Silently drops packets with invalid signatures and fires a security_alert event to the frontend via WebSocket.",
            "Logs all blocked intrusion attempts with timestamp, source ID, and raw payload for forensic auditing.",
            "Prevents Ghost Vehicle Attacks (injection of fake vehicle positions to cause phantom braking).",
        ]),
        ("4", "Collision Detection & ML Prediction Module\n(Scikit-Learn)", [
            "Calculates real-time distance between all active vehicle pairs using the Haversine formula (accounts for Earth's curvature).",
            "Computes closing speed and Time-To-Collision (TTC) based on relative velocity vectors.",
            "Implements Forward Collision Warning (FCW) to alert drivers of imminent front-end crashes.",
            "Implements Emergency Electronic Brake Light (EEBL) to warn trailing drivers of sudden hard braking ahead.",
            "Implements Blind Spot & Lane Change Warnings to detect fast-approaching vehicles in neighboring lanes.",
            "Implements Wrong-Way Driving Alerts to detect oncoming vehicles in divided highways.",
            "Uses a pre-trained Random Forest Classifier to predict collision risk levels: Safe (0), Warning (1), Critical (2).",
            "Generates predictive trajectory lines projecting vehicle positions 5 seconds into the future.",
        ]),
        ("5", "Geofencing Module\n(Backend + Frontend)", [
            "Defines restricted geographic zones as GPS coordinate polygons (e.g., construction sites, school zones).",
            "Performs real-time point-in-polygon checks for every vehicle position update.",
            "Triggers a Geofence Breach alert on the dashboard when a vehicle enters a restricted zone.",
            "Renders the restricted zone as a dashed red boundary on the live map.",
        ]),
        ("6", "Emergency Vehicle Detection Module\n(Backend)", [
            "Identifies vehicles with vehicle_type: Emergency (ambulance, fire truck, police).",
            "Calculates proximity of all nearby vehicles within a 200-meter radius.",
            "Pushes a YIELD RIGHT OF WAY alert to all vehicles in the vicinity via MQTT and WebSocket.",
            "Displays a distinct blue emergency marker with strobe animation on the SCADA dashboard.",
        ]),
        ("7", "SCADA Dashboard Module\n(Frontend — HTML/CSS/JS)", [
            "Full-screen dark-themed HUD (Heads-Up Display) built with HTML5, CSS3, and vanilla JavaScript.",
            "Interactive map powered by Leaflet.js showing real-time vehicle positions as animated radar blips with predictive trajectory lines.",
            "Real-time speed matrix chart (Chart.js) plotting simultaneous speed data for all active vehicles.",
            "Threat Detection panel displaying collision, geofence, cyber-attack, and emergency alerts with severity-coded cards.",
            "Deep Packet Inspection (DPI) Feed showing live scrolling hex-dump of encrypted MQTT payloads.",
            "Network Integrity panel showing average latency, HMAC verification status, and packet drop rate.",
            "V2I Signal Phase and Timing (SPaT) display simulating traffic light interception.",
            "Broadcast Terminal for sending commands to all connected vehicles.",
        ]),
        ("8", "Platooning Coordinator Module\n(Backend + Frontend)", [
            "Detects when two or more vehicles are travelling in the same direction within close proximity (convoy formation).",
            "Calculates aerodynamic drafting benefit percentage based on inter-vehicle gap.",
            "Displays platoon status (Searching / Linked) and drafting efficiency on the dashboard.",
        ]),
        ("9", "Report Generation Module\n(Backend — ReportLab)", [
            "Generates a comprehensive PDF session report on demand via the Export PDF button.",
            "Includes session duration, total vehicles tracked, collision incidents logged, security events, and system performance metrics.",
            "Uses the ReportLab library for professional-grade PDF output.",
        ]),
        ("10", "Database & Logging Module\n(SQLite)", [
            "Automatically initializes the SQLite database schema on first run.",
            "Logs all collision incidents with timestamp, involved vehicles, distance, closing speed, and risk level.",
            "Stores security events (blocked spoofing attempts) for post-incident forensic analysis.",
            "Provides data persistence for the report generation module.",
        ]),
        ("11", "Highway Infrastructure & Toll Service Module (V2I)\n(Backend)", [
            "Uses real-time vehicle GPS coordinates to determine the current highway segment (e.g., NH-44).",
            "Dynamically retrieves upcoming toll plaza locations, distances, and relevant emergency/helpline cell numbers.",
            "Enhances Vehicle-to-Infrastructure (V2I) logistics by providing real-time geographical awareness to the driver.",
        ]),
        ("12", "S-T-S (Speech-to-Speech) Live Call Translator Module\n(AI Integrated)", [
            "Provides an AI-powered communication channel built into the V2X dashboard for emergency and toll service calls.",
            "Intercepts audio and performs real-time Speech-to-Speech translation (e.g., translating regional languages into English/Hindi).",
            "Eliminates language barriers for commercial truck drivers traveling pan-India, ensuring critical emergency information is understood instantly.",
        ]),
    ]

    # Build table rows
    header = [
        Paragraph("<b>S.No</b>", ParagraphStyle('', fontName='Times-Bold', fontSize=10, alignment=TA_CENTER)),
        Paragraph("<b>Module Name</b>", ParagraphStyle('', fontName='Times-Bold', fontSize=10)),
        Paragraph("<b>Functionalities</b>", ParagraphStyle('', fontName='Times-Bold', fontSize=10)),
    ]
    table_data = [header]

    for sno, name, funcs in modules:
        bullets_text = ""
        for i, f in enumerate(funcs):
            bullets_text += f"\u2022 {f}"
            if i < len(funcs) - 1:
                bullets_text += "<br/>"
        
        row = [
            Paragraph(sno, ParagraphStyle('', fontName='Times-Bold', fontSize=10, alignment=TA_CENTER)),
            Paragraph(name.replace('\n', '<br/>'), ParagraphStyle('', fontName='Times-Bold', fontSize=10, leading=13)),
            Paragraph(bullets_text, ParagraphStyle('', fontName='Times-Roman', fontSize=10, leading=13, leftIndent=6)),
        ]
        table_data.append(row)

    mod_table = Table(table_data, colWidths=[12*mm, 45*mm, 113*mm])
    mod_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.85, 0.85, 0.85)),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(mod_table)

    # ── Signature Block ──
    elements.append(Spacer(1, 18*mm))

    sig_data = [
        [
            Paragraph("<b>Student Signatures</b>", ParagraphStyle('', fontName='Times-Bold', fontSize=11, alignment=TA_CENTER)),
            "",
            Paragraph("<b>Guide Signature</b>", ParagraphStyle('', fontName='Times-Bold', fontSize=11, alignment=TA_CENTER)),
        ],
        ["", "", ""],
        ["", "", ""],
        [
            Paragraph("1. ____________________", ParagraphStyle('', fontName='Times-Roman', fontSize=11)),
            Paragraph("2. ____________________", ParagraphStyle('', fontName='Times-Roman', fontSize=11)),
            "",
        ],
        ["", "", ""],
        [
            Paragraph("3. ____________________", ParagraphStyle('', fontName='Times-Roman', fontSize=11)),
            Paragraph("4. ____________________", ParagraphStyle('', fontName='Times-Roman', fontSize=11)),
            Paragraph("_________________________", ParagraphStyle('', fontName='Times-Roman', fontSize=11, alignment=TA_CENTER)),
        ],
        ["", "", ""],
        [
            Paragraph("5. ____________________", ParagraphStyle('', fontName='Times-Roman', fontSize=11)),
            "",
            Paragraph("<b>Mr. Madhu Babu</b>", ParagraphStyle('', fontName='Times-Bold', fontSize=11, alignment=TA_CENTER)),
        ],
        [
            "",
            "",
            Paragraph("Project Guide", ParagraphStyle('', fontName='Times-Roman', fontSize=10, alignment=TA_CENTER)),
        ],
        [
            Paragraph("Date: ______________", ParagraphStyle('', fontName='Times-Roman', fontSize=11)),
            "",
            Paragraph("Date: ______________", ParagraphStyle('', fontName='Times-Roman', fontSize=11, alignment=TA_CENTER)),
        ],
    ]
    sig_table = Table(sig_data, colWidths=[60*mm, 55*mm, 55*mm])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    print("PDF generated: docs/Modules_and_Functionalities.pdf")

if __name__ == "__main__":
    build_pdf()
