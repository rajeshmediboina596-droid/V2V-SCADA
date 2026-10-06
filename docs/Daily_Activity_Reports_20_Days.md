# NETTUR TECHNICAL TRAINING FOUNDATION
## DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
### PROJECT – Daily Activity Reports (20 Pages)

**Project Title:** Internet-Independent V2V Communication & SCADA Safety Monitoring System  
**Project Code:** PRJ_15  
**Project Duration:** 03-03-2026 to 27-03-2026 (20 Working Days)  
**Current Status:** Project In-Progress / Ongoing (Not Fully Completed)

---

## Daily Activity Report — Day 01

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 03-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : Architecture & Hardware Infrastructure

Module Name                 : System Architecture Definition, Feasibility Study & Hardware Pinout Planning

File Name (Physical File Name): docs/modules_and_functionalities.html, v2v.md

Status                      : Completed

Activities carried out in detail:
1. Conducted preliminary requirement analysis and architectural design for an Internet-Independent Vehicle-to-Vehicle (V2V) Communication and SCADA Safety Monitoring System.
   2. Analyzed the upcoming Government of India Ministry of Road Transport and Highways (MoRTH) AIS-230 automotive standard mandate for vehicular safety and inter-vehicle telemetry.
   3. Selected compute and communication components: STM32F103C8T6 (Bluepill) and ESP32 DevKit V1 microcontrollers, U-blox NEO-6M GNSS receivers for 10Hz position acquisition, and local 2.4GHz RF / ESP-NOW wireless links to eliminate cellular and internet latency.
   4. Formulated the high-level 4-tier architecture: Edge Layer (Vehicles), Gateway/RSU Layer (Serial bridge), Transport/Broker Layer (Local Mosquitto MQTT), and Supervisory SCADA Layer (FastAPI + WebSockets + Leaflet.js).
   5. Defined the hardware pinout diagram: GPS TX/RX to microcontroller USART1 (PA9/PA10) at 9600 baud, RF module SPI interface, warning buzzer, and status indicator LEDs.
   6. Formulated team task distribution across the 5 project members and initialized the project documentation.


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 02

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 04-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : Database

Module Name                 : Database Schema Design & SQLite Async Batch Worker Engine

File Name (Physical File Name): backend/database.py

Status                      : Completed

Activities carried out in detail:
1. Designed the relational database schema using SQLite (database/v2v_data.db) for high-speed edge telemetry ingestion and critical vehicular safety incident auditing.
   2. Created database table 'telemetry' (id, vehicle_id, timestamp, lat, lon, speed_kmph, heading_deg, raw_payload) and table 'incidents' (id, timestamp, vehicle_a, vehicle_b, distance, closing_speed, risk_level).
   3. Implemented an asynchronous batching worker thread (_write_worker) with a thread-safe queue.Queue(maxsize=5000) to prevent SQLite database write lock contention during high-frequency (10Hz) incoming streams from multiple concurrent vehicles.
   4. Configured batch flushing logic (_write_batch) collecting up to 250 records per write cycle to optimize disk I/O throughput.
   5. Wrote query helper functions log_telemetry(), log_incident(), and fetch_recent_incidents() for downstream consumption by the SCADA backend and report generator.
   6. Tested write throughput under simulated bursts of 1,000 telemetry messages; confirmed zero thread blocking and 100% data persistence.


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 03

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 05-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : Business logic / Network Transport

Module Name                 : Local MQTT Broker Setup, Topic Hierarchy & Mosquitto Configuration

File Name (Physical File Name): mqtt/mosquitto.conf, mqtt/docker-compose.yml

Status                      : Completed

Activities carried out in detail:
1. Installed and configured the local Eclipse Mosquitto MQTT Broker to operate entirely within an offline, isolated local area network without external internet dependence.
   2. Defined the MQTT topic hierarchy:
      - 'v2v/telemetry': High-frequency vehicle sensor broadcasts to central SCADA.
      - 'v2v/alerts/{vehicle_id}': Targeted collision warnings dispatched to specific vehicle nodes.
      - 'v2v/commands': Broadcast administrative messages to all active vehicular nodes.
   3. Configured mqtt/mosquitto.conf with port 1883, listener rules, persistence storage settings, and maximum connection limits.
   4. Developed mqtt/generate_certs.py and OpenSSL scripts to provision self-signed Certificate Authority (CA), server certificates, and client keys for optional TLS encryption on port 8883.
   5. Verified local pub/sub throughput using command-line Mosquitto tools (mosquitto_sub and mosquitto_pub) with zero message loss across 5,000 test packets.


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 04

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 06-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : Business logic / Security

Module Name                 : Edge Cryptographic Authentication & Anti-Spoofing Engine

File Name (Physical File Name): backend/mqtt_client.py

Status                      : Completed

Activities carried out in detail:
1. Formulated the cyber-defense mechanism to prevent 'Ghost Vehicle Attacks' and Man-in-the-Middle (MitM) coordinate injection on vehicular communication channels.
   2. Implemented the verify_signature() function utilizing the HMAC-SHA256 cryptographic algorithm.
   3. Designed the message signing payload string format: concatenation of vehicle_id, vehicle_type, timestamp, lat, lon, speed_kmph, and heading_deg.
   4. Enforced constant-time cryptographic hash comparison via Python's hmac.compare_digest() to eliminate vulnerability to side-channel timing attacks.
   5. Programmed automated payload rejection: invalid or modified packets are dropped immediately, and a high-priority 'security_alert' event is pushed to the SCADA threat log.
   6. Simulated malicious injection payloads using rogue keys; verified that legitimate packets authenticate in < 15 microseconds while tampered packets trigger instant security drops.


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 05

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 07-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : Hardware & Firmware

Module Name                 : Microcontroller GPS Telemetry Acquisition & NMEA Parser Firmware

File Name (Physical File Name): esp32/firmware/main.ino, stm32/firmware/main.ino

Status                      : Started

Activities carried out in detail:
1. Developed firmware routines for the microcontroller edge node to interface with the U-blox NEO-6M GPS receiver over hardware UART.
   2. Implemented NMEA-0183 sentence parsing (extracting $GPRMC and $GPGGA sentences) using TinyGPS++ library routines to acquire Latitude, Longitude, Ground Speed (km/h), and Compass Heading (degrees).
   3. Formatted telemetry into standard JSON structure containing device metadata, sensor readings, and UNIX millisecond timestamps.
   4. Added cryptographic signing routines in firmware using mbedTLS library to compute the HMAC-SHA256 signature directly on-chip prior to transmission.
   5. Configured timer interrupts to ensure strict 100ms (10Hz) transmission periodicity.
   6. Conducted bench testing with NEO-6M receiver near window; observed cold start TTFF (Time-To-First-Fix) and validated UART parsing stability.


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 06

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 09-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : Business logic / Hardware Interface

Module Name                 : Roadside Unit (RSU) Gateway & Serial-to-MQTT Bridge

File Name (Physical File Name): backend/serial_to_mqtt.py

Status                      : Completed

Activities carried out in detail:
1. Developed the hardware gateway communication daemon backend/serial_to_mqtt.py to bridge physical vehicle RF radio signals to the local SCADA MQTT broker.
   2. Implemented serial port discovery and communication routines using pyserial at 115200 baud rate with non-blocking read timeouts.
   3. Created raw serial stream buffering and payload frame boundary detection (checking '{' and '}' delimiters) to filter out line noise and incomplete RF packets.
   4. Bound the serial reader thread to a persistent Paho MQTT client publishing valid JSON telemetry frames onto topic 'v2v/telemetry'.
   5. Added automatic reconnection handling to safeguard against accidental USB cable disconnection or port reset.
   6. Tested end-to-end data flow: injected raw test telemetry strings from microcontroller serial output and confirmed immediate reception by the MQTT broker in < 5 milliseconds.


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 07

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 10-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : Business logic

Module Name                 : Haversine Spherical Distance Calculation & Relative Motion Vectors

File Name (Physical File Name): backend/mqtt_client.py

Status                      : Completed

Activities carried out in detail:
1. Implemented mathematical models for real-time spatial positioning of moving vehicles on the spherical surface of the Earth.
   2. Programmed the haversine() function in backend/mqtt_client.py, calculating great-circle distance between two geographic coordinates using Earth radius R = 6,371,000 meters.
   3. Formulated 2D Cartesian coordinate transformation from geodesic coordinates (Lat/Lon) to local tangent plane meters (dx, dy) taking into account latitude-dependent longitudinal shrinkage (cos(mid_lat)).
   4. Derived vehicle velocity vectors (vx = s * cos(theta), vy = s * sin(theta)) from speed in m/s and compass heading.
   5. Implemented relative velocity dot-product math to compute instantaneous closing speed between any two vehicular nodes.
   6. Unit tested with known coordinate pairs; confirmed geometric error is under 0.05% compared to Vincenty's geodetic formula over 500-meter ranges.


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 08

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 11-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : Business logic / Machine Learning

Module Name                 : Time-To-Collision (TTC) Dynamics & Synthetic Training Dataset Generation

File Name (Physical File Name): ml/train_model.py

Status                      : Completed

Activities carried out in detail:
1. Analyzed the physical limitations of purely static proximity thresholds in dynamic vehicular environments (e.g., two cars stopped 5 meters apart vs. two cars heading towards each other at 80 km/h).
   2. Formulated Time-To-Collision equation: TTC = Distance / Closing Speed.
   3. Developed ml/train_model.py to synthesize a comprehensive training dataset spanning 10,000 realistic traffic scenarios.
   4. Classified risks into three distinct safety tiers:
      - Level 0 (Safe): Large distance or negative/zero closing speed (TTC > 5.0s).
      - Level 1 (Warning): Moderate closing speed with diminishing headway (2.0s <= TTC <= 5.0s).
      - Level 2 (Critical): Imminent impact requiring automated emergency braking (0s < TTC < 2.0s).
   5. Incorporated Gaussian measurement noise to simulate real-world GPS position jitter and velocity estimation variations.
   6. Verified class balance across the synthesized dataset using NumPy and Pandas summary statistics.


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 09

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 12-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : Business logic / Machine Learning

Module Name                 : Random Forest Collision Risk Classifier Training & Model Serialization

File Name (Physical File Name): ml/train_model.py, ml/collision_risk_model.pkl

Status                      : Completed

Activities carried out in detail:
1. Implemented the Machine Learning pipeline using scikit-learn to train a high-accuracy tabular classifier for predictive collision risk estimation.
   2. Evaluated candidate algorithms (Logistic Regression, Decision Trees, Random Forest); selected Random Forest Classifier with 100 estimators for superior non-linear decision boundary modeling.
   3. Executed 80/20 train-test split and performed 5-fold cross-validation.
   4. Achieved >99% classification accuracy, precision, and recall on the held-out test dataset across all three risk categories.
   5. Exported and serialized the trained model to ml/collision_risk_model.pkl using Python's pickle library for low-latency in-memory execution.
   6. Benchmarked inference latency: verified that model prediction executes in under 0.8 milliseconds per vehicle pair, well within the 100ms budget of 10Hz telemetry.


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 10

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 13-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : Business logic

Module Name                 : Hybrid Collision Prediction Engine Integration & Safe Fallback

File Name (Physical File Name): ml/collision_model.py, backend/mqtt_client.py

Status                      : Completed

Activities carried out in detail:
1. Created the wrapper class CollisionPredictor in ml/collision_model.py to decouple model inference from backend transport logic.
   2. Implemented robust error handling: if the pre-trained pickle model is missing or corrupted, the system gracefully falls back to deterministic rule-based TTC evaluation, ensuring zero downtime.
   3. Integrated compute_collision_risk() into backend/mqtt_client.py to evaluate every active vehicle against all nearby peers upon every incoming telemetry update.
   4. Added pairwise throttling logic (PAIR_EVALUATION_INTERVAL_SECONDS = 0.25) to cap algorithmic complexity at scale without compromising reaction time.
   5. Configured MQTT alert dispatch: when risk level > 0, an alert JSON payload is published to 'v2v/alerts/{vehicle_id}' and queued for frontend SCADA notification.
   6. Conducted end-to-end integration tests simulating two converging vehicles; verified alert generation triggered at exactly 4.8 seconds prior to simulated impact.


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 11

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 16-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : Business logic / Web Application

Module Name                 : FastAPI Asynchronous Core, Security Middlewares & WebSocket Broadcast Hub

File Name (Physical File Name): backend/main.py

Status                      : Completed

Activities carried out in detail:
1. Built the centralized SCADA web service using the FastAPI asynchronous framework (backend/main.py).
   2. Configured CORS middleware and essential cybersecurity HTTP response headers (X-Frame-Options: DENY, X-Content-Type-Options: nosniff, Strict-Transport-Security).
   3. Mounted static directories /css and /js to serve frontend SCADA assets directly from local storage without external CDN dependencies.
   4. Implemented the bidirectional WebSocket endpoint /ws managing active browser client sessions.
   5. Developed the asynchronous consumer coroutine broadcast_messages() utilizing asyncio.Queue to dispatch MQTT telemetry and threat events to all connected clients at 60 FPS.
   6. Added client disconnection detection and dead socket cleanup logic to prevent memory leaks during long-running operational sessions.
   7. Tested WebSocket concurrency with multiple simultaneous browser tabs; recorded smooth 60Hz message streaming.


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 12

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 17-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : Business logic

Module Name                 : Geofencing Engine & Ray-Casting Point-in-Polygon Detection

File Name (Physical File Name): backend/mqtt_client.py

Status                      : Completed

Activities carried out in detail:
1. Designed the SCADA Geofencing subsystem to enforce restricted geographic zones (construction sites, high-pedestrian school zones, VIP security perimeters).
   2. Defined GPS coordinate boundary polygon RESTRICTED_ZONE in backend/mqtt_client.py spanning 4 GPS vertices.
   3. Programmed the Ray-Casting algorithm (is_in_polygon(lat, lon, poly)) to determine whether any vehicle coordinates lie inside or outside the arbitrary polygon boundary.
   4. Configured high-priority alert generation: upon zone violation, the system generates a risk_level: 3 (Geofence Breach) alarm targeting the offending vehicle.
   5. Added alert dispatch to MQTT topic 'v2v/alerts/{vid}' and immediate WebSocket broadcast to SCADA operators.
   6. Verified edge cases: tested vehicle coordinates strictly on boundaries, outside, and inside the polygon; confirmed 100% detection accuracy.


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 13

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 18-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : Business logic

Module Name                 : Emergency Vehicle Priority Detection & Yield Advisory Override

File Name (Physical File Name): backend/mqtt_client.py

Status                      : Completed

Activities carried out in detail:
1. Implemented specialized handling for emergency vehicles (ambulances, fire engines, police interceptors) identified by vehicle_type: 'Emergency'.
   2. Programmed proximity scanning logic: when an emergency vehicle is detected within a 200-meter radius of any civilian passenger vehicle, an automated priority override is triggered.
   3. Created alert class risk_level: 4 ('Emergency Yield Right of Way') warning civilian drivers to safely pull over or yield lanes.
   4. Added rate-limiting registry (ALERT_RESEND_INTERVAL_SECONDS = 1.0) to avoid flooding network bandwidth while maintaining persistent situational awareness.
   5. Integrated the emergency alert pipeline into the SCADA event feed to notify dispatchers of active siren/emergency corridors.
   6. Tested multi-vehicle scenarios involving one emergency unit approaching two passenger cars; confirmed both passenger vehicles received yield commands simultaneously.


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 14

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 19-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : GUI (Frontend)

Module Name                 : SCADA HUD Interface Layout, Cyberpunk Styling & DOM Architecture

File Name (Physical File Name): frontend/index.html, frontend/css/style.css

Status                      : Completed

Activities carried out in detail:
1. Developed the responsive SCADA Heads-Up Display (HUD) interface using HTML5 semantic elements and vanilla CSS3.
   2. Implemented an industrial dark-themed aesthetic with cyan/amber HUD accents, high-contrast indicators, and glassmorphic telemetry cards.
   3. Structured the operational dashboard layout:
      - Header status bar: System mode toggle (LIVE / DEMO), connection status, clock, and emergency PDF export trigger.
      - Central operational viewport: Full-screen interactive tactical map.
      - Left telemetry sidebar: Active vehicle count, average network latency, and live speed telemetry matrix.
      - Right safety & security drawer: Real-time threat detection feed, geofence alarm cards, and Deep Packet Inspection (DPI) monitor.
      - Bottom command console: V2I traffic signal timing and broadcast override terminal.
   4. Styled custom warning flash animations for Level 2 Critical alarms and blue strobe effects for Emergency vehicles.
   5. Validated responsive layout rendering across various monitor resolutions (1080p, 1440p, 4K).


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 15

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 20-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : GUI (Frontend)

Module Name                 : Leaflet.js Tactical GIS Map & Real-Time Radar Blip Marker Engine

File Name (Physical File Name): frontend/js/app.js

Status                      : Completed

Activities carried out in detail:
1. Integrated the Leaflet.js open-source GIS mapping library within frontend/js/app.js to visualize vehicular positions in real time.
   2. Configured dark-mode tile layers using CartoDB Dark Matter tiles with local caching fallback for offline operation.
   3. Created custom SVG marker blips with directional rotation matching vehicle compass heading (heading_deg).
   4. Implemented dynamic vehicle trail visualization: rendering color-coded breadcrumb lines showing historical trajectories of active vehicles.
   5. Added dynamic geofence polygon overlays rendering restricted zone boundaries with glowing dashed borders.
   6. Programmed marker interpolation to provide smooth vehicle movement across consecutive 10Hz updates without visual stutter.
   7. Tested map rendering with 10 concurrently moving vehicle markers; observed smooth 60 FPS canvas performance.


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 16

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 21-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : GUI / Business logic

Module Name                 : OSRM Road-Snapping & Curvature Waypoint Interpolation

File Name (Physical File Name): backend/routes.json, backend/main.py, frontend/js/app.js

Status                      : Completed

Activities carried out in detail:
1. Addressed the critical issue of vehicular map drift: vehicles moving in straight Cartesian lines often appeared to drive across buildings and non-road terrain.
   2. Integrated Open Source Routing Machine (OSRM) geometry to snap simulated and captured vehicular paths to actual real-world street networks.
   3. Generated pre-computed polyline waypoints for 4 distinct road corridors and stored them in backend/routes.json.
   4. Updated run_demo_simulation() in backend/main.py to iterate along road polyline nodes, automatically computing smooth heading angles from tangent vectors.
   5. Implemented predictive trajectory projection lines in frontend/js/app.js: projecting vehicle paths 5 seconds into the future along road vectors.
   6. Evaluated visual tracking realism; verified that vehicles adhere strictly to road lanes and intersection turn geometries.


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 17

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 23-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : GUI & Security

Module Name                 : Deep Packet Inspection (DPI) Hex Stream & Network Integrity Monitor

File Name (Physical File Name): frontend/js/app.js, frontend/index.html

Status                      : Completed

Activities carried out in detail:
1. Implemented the Deep Packet Inspection (DPI) hex-dump terminal on the SCADA dashboard to provide network transparency for security auditing.
   2. Programmed frontend routines to format incoming JSON payloads and cryptographic hashes into formatted hex byte streams with timestamp tags.
   3. Built the Network Integrity metric widgets:
      - Average network transit latency calculation (comparing packet timestamps against local browser receipt clock).
      - Cryptographic signature pass/drop counter.
      - Packet throughput rate (packets per second).
   4. Integrated the 'Simulate Cyber Spoofing Attack' UI button in frontend/index.html calling backend /api/spoof.
   5. Verified live security response: upon clicking spoof button, the dashboard immediately triggers an audible alarm, displays a red rogue attack banner, and prints the rejected raw packet in the DPI hex log.


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 18

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 24-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : Business logic / Reporting

Module Name                 : Automated Incident Reporting & PDF Document Generation Engine

File Name (Physical File Name): backend/report_generator.py, backend/main.py

Status                      : Completed

Activities carried out in detail:
1. Developed the automated PDF incident reporting module backend/report_generator.py utilizing Python's reportlab engine.
   2. Structured the formal incident report document layout:
      - Header: SCADA Safety Incident & Telemetry Audit Log with NTTF project metadata.
      - Executive Summary Table: Total active session duration, total vehicle telemetry packets processed, collision risks logged, and cyber intrusions blocked.
      - Incident Details Table: Chronological list of near-miss and critical collision warnings with vehicle IDs, timestamp, minimum distance (m), and closing speed.
      - Security Audit Table: Log of blocked rogue packets and signature validation failures.
   3. Implemented backend endpoints: POST /api/report to compile the report from SQLite database tables, and GET /api/download/{filename} to serve the generated PDF.
   4. Verified generated PDF formatting and page layout across multiple session runs; verified PDF generated cleanly in reports/ directory in < 400ms.


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 19

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 25-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : Business logic / Testing

Module Name                 : Multi-Vehicle 20-Node Traffic Load Simulation & Performance Benchmarking

File Name (Physical File Name): esp32/simulator.py, backend/main.py

Status                      : Reviewing

Activities carried out in detail:
1. Formulated a comprehensive stress-testing suite to benchmark system performance under heavy vehicular traffic conditions.
   2. Expanded run_demo_simulation() to simulate 20 concurrent vehicles: 4 OSRM road-snapped vehicles and 16 linear-drift vehicles moving across the operational zone.
   3. Each simulated vehicle computes genuine HMAC-SHA256 signatures and broadcasts telemetry at 10Hz, generating 200 packets per second across the local MQTT broker.
   4. Monitored system metrics:
      - Backend CPU utilization remained under 12% on host workstation.
      - SQLite batch worker kept queue size below 50 items with zero disk lock exceptions.
      - End-to-end telemetry latency averaged 18 to 28 milliseconds.
      - WebSocket message streaming held consistent 60 FPS without frame drops.
   5. Identified potential bottleneck in pairwise distance computation with N > 30 vehicles; initiated code review for spatial indexing optimization.


Project Guide                                                 Project Co-ordinator
```

---

## Daily Activity Report — Day 20

```
                        NETTUR TECHNICAL TRAINING FOUNDATION                
                        DIPLOMA IN COMPUTER ENGINEERING AND IT INFRASTRUCTURE
                                 PROJECT – Daily Activity Report

Project Title: Internet-Independent V2V Communication & SCADA Safety Monitoring System
Project Code: PRJ_15                                        Date: 27-03-2026

Members Present:
TOKEN NUMBER    NEC0824051       NEC0824065        NEC0824080                     NEC0824061    NEC0822087
NAME            T R MANJUNATH    MEDIBOINA RAJESH  MADIREDDY CHENNAKESAVA REDDY   THILAK RAJ    Lakshmipathi.T

Layer                       : Hardware, Firmware & Integration

Module Name                 : Hardware-in-the-Loop (HIL) Breadboard RF Integration & Pending Work Review

File Name (Physical File Name): esp32/firmware/main.ino, stm32/firmware/main.ino, backend/serial_to_mqtt.py

Status                      : Started / Reviewing

Activities carried out in detail:
1. Set up the Hardware-in-the-Loop (HIL) breadboard testbench connecting physical ESP32 and STM32 Bluepill microcontrollers with U-blox NEO-6M GPS modules.
   2. Flashed updated firmware with hardware UART interrupt routines for low-jitter NMEA sentence acquisition.
   3. Interfaced the physical Roadside Unit (RSU) microcontroller to the workstation via USB Serial and launched backend/serial_to_mqtt.py.
   4. Conducted preliminary RF packet broadcast tests between two physical breadboard nodes; verified successful reception and forwarding of real hardware GPS packets to the SCADA dashboard.
   5. Reviewed current project completion status with the Project Guide:
      - Completed Subsystems: Local MQTT broker architecture, cryptographic HMAC-SHA256 verification, hybrid ML collision risk model, SCADA HUD frontend, OSRM road snapping, SQLite batch logger, and automated PDF reporting.
      - Ongoing / Incomplete Work: Physical multi-node RF range optimization (field testing with 3+ moving vehicles outdoors), audio-visual buzzer/OLED alert latency tuning on the vehicle dashboard, and compliance mapping against the draft AIS-230 specification.
   6. Outlined the remaining development roadmap and assigned tasks for subsequent phases.


Project Guide                                                 Project Co-ordinator
```

---
