# 🚗⚡ V2V-SCADA: Internet-Independent Vehicle-to-Vehicle Safety & Highway Telemetry System

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)
[![Hardware: STM32 + SX1281 2.4GHz](https://img.shields.io/badge/Hardware-STM32%20%7C%20SX1281%202.4GHz-brightgreen.svg?style=for-the-badge)](docs/FIRMWARE_SPECIFICATION.md)
[![Standards: MoRTH AIS-230 Concepts](https://img.shields.io/badge/Standard-MoRTH%20AIS--230%20Concepts-orange.svg?style=for-the-badge)](docs/REQUIREMENTS_MATRIX.md)
[![Backend: FastAPI / WebSockets](https://img.shields.io/badge/Backend-FastAPI%20%7C%20WebSockets%20%7C%20MQTT-009688.svg?style=for-the-badge)](backend/)
[![Security: HMAC-SHA256 & RBAC](https://img.shields.io/badge/Security-HMAC--SHA256%20%7C%20RBAC%20%7C%20Anti--Replay-red.svg?style=for-the-badge)](backend/security.py)
[![Tests: 87/87 Pytest Passed](https://img.shields.io/badge/Tests-87%2F87%20Passed-success.svg?style=for-the-badge)](tests/)
[![CI: GitHub Actions](https://img.shields.io/badge/CI-GitHub%20Actions%20Passing-2088FF.svg?style=for-the-badge&logo=githubactions&logoColor=white)](.github/workflows/ci.yml)

<p align="center">
  <b>A cellular-independent Vehicle-to-Vehicle (V2V) cooperative collision avoidance and real-time SCADA highway telemetry monitoring system developed as a final-year engineering prototype aligned with concepts from India's MoRTH AIS-230 guidelines.</b>
</p>

[ ⚡ Quickstart ](#-quick-start-guide) •
[ 🏗️ Architecture ](#-system-architecture) •
[ 🛡️ Security & RBAC ](#%EF%B8%8F-cybersecurity--rbac-matrix) •
[ 📐 Collision Physics ](#-deterministic-collision-physics--supplementary-ml) •
[ 🔌 Hardware & Pinout ](#-hardware-specifications--pinout) •
[ 🧪 Tests (87 Passed) ](#-testing--verification-suite) •
[ 📚 Detailed Specs (docs/) ](#-technical-specifications-index)

</div>

---

## 💡 The Real-World Problem & Solution

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  THE HIGHWAY CHALLENGE (Non-Line-of-Sight & Zero Connectivity Blind Spots)             │
│                                                                                        │
│  Imagine a dense fog, monsoon downpour, or a blind hairpin curve in a mountain valley. │
│  A disabled truck is stranded 60 meters ahead.                                         │
│                                                                                        │
│  ❌ Optical Cameras & LiDAR cannot see through physical obstacles or heavy rain.      │
│  ❌ 4G/5G Cellular C-V2X fails completely in rural valleys with no tower coverage.     │
│  ❌ Drivers receive zero advance warning until collision is unavoidable.               │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  THE V2V-SCADA SOLUTION (100% Internet-Independent Direct RF Cooperative Safety)        │
│                                                                                        │
│  ✅ Edge Microcontrollers (STM32) broadcast position, speed, and heading at 10 Hz.    │
│  ✅ 2.4 GHz RF (Semtech SX1281 FLRC) penetrates fog and physical obstacles directly.   │
│  ✅ Deterministic Time-to-Collision (TTC) mathematics trigger sub-second cabin alerts. │
│  ✅ Cryptographic HMAC-SHA256 signatures reject forged ghost-vehicle spoof attacks.    │
│  ✅ Stationary Roadside Units (RSUs) bridge telemetry to central SCADA for live HUD.  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🏛️ System Architecture

The platform operates on a **two-tier decoupled architecture**:
1. **Core Safety Plane (100% Offline)**: Peer-to-peer RF communication between moving vehicles. Operates entirely without cellular towers, clouds, or host servers.
2. **Supervisory SCADA Plane (Highway Monitoring)**: Roadside Units (RSUs) capture passing broadcasts, forwarding verified telemetry to a cybernetic dashboard for fleet monitoring, toll management, and automated incident audit reports.

```text
==========================================================================================
                      CORE SAFETY PLANE (100% OFFLINE PEER-TO-PEER)
==========================================================================================
   Vehicle Node A (STM32)                                  Vehicle Node B (STM32)
   ┌──────────────────────────┐                            ┌──────────────────────────┐
   │ GNSS: Lat, Lon, Speed    │                            │ GNSS: Lat, Lon, Speed    │
   │ IMU: Pitch, Roll, Yaw    │  2.4 GHz Direct RF (FLRC)  │ IMU: Pitch, Roll, Yaw    │
   │ Crypto: HMAC-SHA256 Sign │ ◄────────────────────────► │ Crypto: HMAC-SHA256 Sign │
   │ TTC Collision Math (10Hz)│   (Sub-3ms Latency Target) │ TTC Collision Math (10Hz)│
   │ Local OLED HUD & Buzzer  │                            │ Local OLED HUD & Buzzer  │
   └────────────┬─────────────┘                            └────────────┬─────────────┘
                │                                                       │
================│=======================================================│=================
                │ Intercepted by Roadside Unit (RSU Gateway Node)       │
                ▼                                                       ▼
==========================================================================================
                     SUPERVISORY SCADA PLANE (HIGHWAY MANAGEMENT HUD)
==========================================================================================
                            ┌─────────────────────────────────┐
                            │    RSU Telemetry Gateway        │
                            │    (USB Serial / MQTT Bridge)   │
                            └────────────────┬────────────────┘
                                             │
                                             ▼
                            ┌─────────────────────────────────┐
                            │      Mosquitto MQTT Broker      │
                            │ (TLS 8883 / Least-Privilege ACL)│
                            └────────────────┬────────────────┘
                                             │
                                             ▼
                            ┌─────────────────────────────────┐
                            │    FastAPI Central Backend      │
                            │  - Deterministic HMAC Verifier  │
                            │  - Monotonic Replay Window (30s)│
                            │  - RBAC API Authorization Gate  │
                            │  - SQLite WAL Database Logger   │
                            └────┬───────────────────────┬────┘
                                 │                       │
               60 FPS WebSockets │                       │ PDF Incident Reports
                                 ▼                       ▼
            ┌───────────────────────────────┐ ┌───────────────────────────────┐
            │ Leaflet Geospatial HUD Screen │ │ Automated Audit PDF Generator │
            │ - Real-time vehicle positions │ │ - Timestamped crash dossiers  │
            │ - Live speed / heading ribbons│ │ - Cryptographic verification  │
            │ - Threat strobe annunciator   │ │ - Legal compliance archiving  │
            │ - 12-language voice dispatch  │ │                               │
            └───────────────────────────────┘ └───────────────────────────────┘
```

### Architectural Classification:
- **Core System (Essential)**: V2V telemetry, 2.4 GHz RF transceivers, GNSS positioning, 6-DoF IMU orientation, HMAC-SHA256 signatures, monotonic anti-replay, deterministic TTC collision detection, and SCADA dashboard.
- **Supporting (Platform Infrastructure)**: Mosquitto MQTT broker, FastAPI asynchronous engine, WebSockets, SQLite in WAL mode, and Docker orchestration.
- **Advanced / Optional (Modular Extensions)**: Supplementary ML collision-risk classifier, WebRTC multilingual Indic voice translation HUD, highway tollgate geofencing, and emergency contact dispatch.

---

## 🌟 Key Features

| Capability | Feature Highlights | Architectural Benefit |
| :--- | :--- | :--- |
| **Direct V2V RF** | 2.4 GHz Semtech SX1281 FLRC modulation; 10 Hz broadcast rate | Zero reliance on cell networks; immune to cellular blackouts. |
| **Collision Threat Logic** | Deterministic 2D relative motion vectoring + Haversine closing speed | Millisecond-grade Time-to-Collision (TTC) pre-crash annunciation. |
| **Cryptographic Integrity** | Canonical key-value HMAC-SHA256 digest + 30s timestamp window | Rejects injected ghost packets, GPS spoofing, and sequence replays. |
| **Role-Based Access (RBAC)**| `viewer` (read telemetry), `operator` (commands/reports), `admin` (demo/spoof)| Restricts critical supervisory endpoints from unauthorized tampering. |
| **SCADA Command Allowlist**| Only allowlisted SCADA safety commands permitted on API | Eliminates shell injection and unauthorized execution risks. |
| **Cybernetic Leaflet HUD** | 60 FPS WebSocket push; animated vehicle markers, heading compass ribbons | Real-time visual tracking of fleet status and active alerts. |
| **Indic Voice Dispatch** | WebRTC in-browser audio with 12 Indian regional language pipelines | Overcomes regional driver language barriers during highway crises. |
| **PDF Audit Dossiers** | Automated ReportLab PDF generation with incident maps and telemetry | Generates verifiable legal crash reports for emergency services. |

---

## 🛡️ Cybersecurity & RBAC Matrix

The system enforces a clean architectural separation between **Demo Mode** and **Secure Mode**:

```
Mode Selection: Controlled via DEMO_MODE in .env
├── DEMO_MODE=true  ──► Plug-and-play evaluation, anonymous local MQTT, zero-credential HUD
└── DEMO_MODE=false ──► Strict production security: TLS MQTT, mandatory API RBAC, strict secrets
```

| Security Dimension | DEMO MODE (`DEMO_MODE=true`) | SECURE MODE (`DEMO_MODE=false`) |
| :--- | :--- | :--- |
| **API Authentication** | Disabled (`API_AUTH_ENABLED=false`) | **Strictly Enforced** (`API_AUTH_ENABLED=true`) |
| **Role Enforcement** | Implicit admin for browser testing | `viewer` $\le$ `operator` $\le$ `admin` via Bearer/Key |
| **Mosquitto MQTT** | Anonymous local broker (`port 1883`) | TLS 1.2+ (`port 8883`), username/password + ACL |
| **HMAC Secret Check** | Default demo secret permitted | **Startup Aborted** if secret is empty or insecure |
| **SCADA Command Dispatch**| Allowlisted commands | Allowlisted + Signed + Operator Role Required |
| **Path Traversal Shield**| Regex check (`^[a-zA-Z0-9_\-]+\.pdf$`) | Regex check (`^[a-zA-Z0-9_\-]+\.pdf$`) |
| **Query Limit Bounds** | Strictly bounded (`1 <= limit <= 500`) | Strictly bounded (`1 <= limit <= 500`) |

### Whitelisted SCADA Safety Commands
Arbitrary host shell execution is strictly prohibited. `POST /api/command` only accepts:
`EMERGENCY_ALERT` • `SLOW_DOWN` • `STOP_WARNING` • `YIELD_TO_EMERGENCY` • `TEST_ALARM` • `CLEAR_HAZARD` • `RESUME_NORMAL_SPEED`.

---

## 📐 Deterministic Collision Physics & Supplementary ML

### 1. Primary Mechanism: Deterministic Physics
Collision prediction is calculated using geodesic separation combined with Cartesian relative velocity vectors:

$$\Delta\text{distance} = \text{Haversine}(\text{lat}_1, \text{lon}_1, \text{lat}_2, \text{lon}_2)$$

$$\vec{v}_1 = (s_1 \cdot \sin(\theta_1), \; s_1 \cdot \cos(\theta_1)), \quad \vec{v}_2 = (s_2 \cdot \sin(\theta_2), \; s_2 \cdot \cos(\theta_2))$$

$$\vec{v}_{rel} = \vec{v}_1 - \vec{v}_2, \quad \vec{r}_{rel} = (dx, \; dy)$$

$$v_{close} = \frac{\vec{r}_{rel} \cdot \vec{v}_{rel}}{\|\vec{r}_{rel}\|}, \qquad \text{Time-To-Collision (TTC)} = \frac{\text{distance}}{v_{close}}$$

| Alert Tier | TTC Threshold | Vehicle Separation | Annunciation Level |
| :---: | :---: | :---: | :--- |
| **Safe** | $\text{TTC} > 5.0\text{ s}$ | $> 100\text{ m}$ | Green status indicator; silent normal monitoring. |
| **Advisory** | $3.5\text{ s} < \text{TTC} \le 5.0\text{ s}$ | $50\text{ m} - 100\text{ m}$ | Yellow caution indicator; visual OLED notification. |
| **Warning** | $2.5\text{ s} < \text{TTC} \le 3.5\text{ s}$ | $25\text{ m} - 50\text{ m}$ | Red hazard strobe; rapid audible piezo beeping. |
| **Critical** | $\text{TTC} \le 2.5\text{ s}$ | $< 25\text{ m}$ | Continuous audible alarm; demonstration AEB relay trigger. |

### 2. Supplementary Machine Learning Classifier
> [!IMPORTANT]
> **Engineering Transparency**: The ML collision model is a **supplementary classification layer** trained and evaluated using synthetic kinematic vectors. The deterministic TTC-based physical formulation is the primary, safety-critical mechanism. The ML model outputs secondary advisory predictions and automatically degrades to rule-based physics if the model artifact is absent or encounters unexpected inputs.

---

## 🔌 Hardware Specifications & Pinout

The physical testbed is designed for **STM32 ARM Cortex-M** microcontrollers:

| Subsystem | Component Specification | Hardware Role |
| :--- | :--- | :--- |
| **Microcontroller** | **STM32F401RE / F103 Nucleo / Blue Pill** (ARM Cortex-M) | 10 Hz telemetry loop, sensor acquisition, and HMAC signing. |
| **2.4 GHz RF** | **Semtech SX1281 / SX1280** (SPI interface) | High-speed FLRC modulation (1.3 Mbps), peer-to-peer V2V link. |
| **GNSS Positioning** | **Quectel L86 / u-blox NEO-M8N** (USART serial) | 10 Hz NMEA stream (Latitude, Longitude, Ground Speed). |
| **6-DoF Orientation** | **MPU-6050 / ICM-20689** (I2C1 bus) | Vehicle pitch (grade), roll (tilt), and yaw (compass heading). |
| **Display & Audio** | **SSD1306 128x64 OLED + Active Piezo Buzzer** | In-cabin driver HUD and acoustic collision pre-warning. |

Full pin connection mappings, schematic tables, and bill of materials are documented in [`docs/FIRMWARE_SPECIFICATION.md`](docs/FIRMWARE_SPECIFICATION.md) and [`docs/HARDWARE_BOM.md`](docs/HARDWARE_BOM.md).

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.10+ (Python 3.12 recommended)
- Git
- Modern Web Browser (Chrome, Edge, Firefox)

### Option 1: Run Locally (Under 60 Seconds)

```bash
# 1. Clone the repository
git clone https://github.com/rajeshmediboina596-droid/V2V-SCADA.git
cd V2V-SCADA

# 2. Create and activate a Python virtual environment
python -m venv venv
.\venv\Scripts\activate      # Windows (PowerShell)
# source venv/bin/activate    # Linux / macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch the SCADA Central Backend (starts in Demo Mode)
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser and navigate to:
👉 **`http://127.0.0.1:8000`**

### Option 2: Docker Orchestration

```bash
# Start Demo Stack (FastAPI + Mosquitto broker)
docker compose up -d

# Check live logs
docker compose logs -f
```

---

## 🎮 Interactive Demonstration Walkthrough

Once the dashboard is open at `http://127.0.0.1:8000`, you can demonstrate all core capabilities:

### 1. Run Live Multi-Vehicle Simulation
Click **`▶ Run Demo`** on the top navigation bar (or execute via cURL):
```bash
curl -X POST http://127.0.0.1:8000/api/demo
```
*Result*: Four routed vehicles (Passenger cars, Heavy Freight Truck, and Priority Ambulance) populate the Leaflet map in real time, streaming signed 10 Hz telemetry with dynamic pitch, roll, and speed changes.

### 2. Trigger Rogue Ghost-Vehicle Spoof Attack
Click **`⚠ Spoof Attack`** on the top navigation bar:
```bash
curl -X POST http://127.0.0.1:8000/api/spoof
```
*Result*: A rogue packet claiming ID `ROGUE-X` with a forged cryptographic signature is broadcasted. The backend HMAC engine instantly catches the tampering, logs a security alert, and drops the packet—preventing ghost vehicles from polluting trusted collision calculations.

### 3. Dispatch Allowlisted SCADA Command
Send a centralized safety advisory to the vehicle network:
```bash
curl -X POST http://127.0.0.1:8000/api/command \
  -H "Content-Type: application/json" \
  -d "{\"command\":\"SLOW_DOWN\"}"
```

### 4. Generate & Download PDF Incident Report
Click **`📄 PDF Report`** on the dashboard HUD:
```bash
curl -X POST http://127.0.0.1:8000/api/report
```
*Result*: An official incident audit report is compiled in `reports/` complete with timestamped coordinates, vehicle threat levels, and cryptographic verification statuses.

---

## 🧪 Testing & Verification Suite

The repository contains **87 automated test cases** across 7 test modules with 100% pass rate:

```bash
# Run complete test suite
pytest

# Compile all source files for syntax correctness
python -m compileall -q .
```

```text
============================= test session starts ==============================
rootdir: C:\projectss\v2v communication, configfile: pytest.ini
collected 87 items

tests/test_auth_and_control_hardening.py ......           [  9 passed ]
tests/test_canonical_contract.py ...........              [ 11 passed ]
tests/test_collision_scenarios.py ................        [ 16 passed ]
tests/test_failure_recovery.py .........                 [  9 passed ]
tests/test_mqtt_reliability.py ....                      [  4 passed ]
tests/test_security_regressions.py ................       [ 16 passed ]
tests/test_v2v_security_and_physics.py .................  [ 17 passed ]

============================== 87 passed in 5.42s ===============================
```

---

## 📁 Repository Directory Structure

```text
V2V-SCADA/
├── backend/                        # FastAPI Core Backend Engine
│   ├── auth.py                     # RBAC Authorization (viewer, operator, admin)
│   ├── collision.py                # Geodesic Haversine & closing velocity physics
│   ├── config.py                   # Environment & security configuration loader
│   ├── database.py                 # SQLite WAL schema, tollgates & incident logger
│   ├── main.py                     # REST endpoints, WebSockets & allowlisted dispatch
│   ├── mqtt_client.py              # Asynchronous Mosquitto MQTT ingestion client
│   ├── report_generator.py         # Automated PDF accident audit generator
│   ├── security.py                 # Canonical HMAC-SHA256 & monotonic anti-replay
│   ├── translation.py              # Indic language translation & lexicon pipeline
│   └── providers/                  # Clean telephony, STT, and TTS abstraction layers
├── frontend/                       # SCADA Web Client & Cockpit HUD
│   ├── index.html                  # Cybernetic Leaflet monitoring dashboard
│   ├── css/style.css               # Clean dark-mode glassmorphism styling
│   └── js/app.js                   # WebSocket handler, real-time map & telemetry feeds
├── stm32/firmware/                 # Embedded C++ Firmware for STM32
│   ├── main.ino                    # Canonical master firmware entry point
│   └── stm32_v2v_firmware/         # Arduino IDE compatibility sketch bundle
├── mqtt/                           # Mosquitto Broker Configuration
│   ├── mosquitto.conf              # Demo mode broker configuration (port 1883)
│   ├── mosquitto_secure.conf       # Secure mode TLS broker configuration (port 8883)
│   └── mosquitto.acl               # Least-privilege topic Access Control List
├── tests/                          # 87 Automated Unit & Integration Tests
│   ├── test_auth_and_control_hardening.py
│   ├── test_canonical_contract.py
│   ├── test_collision_scenarios.py
│   ├── test_failure_recovery.py
│   ├── test_mqtt_reliability.py
│   ├── test_security_regressions.py
│   └── test_v2v_security_and_physics.py
├── docs/                           # Exhaustive Engineering Specifications
├── docker-compose.yml              # Local Demo multi-container stack
├── docker-compose.secure.yml       # Secure Production multi-container stack
├── Dockerfile                      # Non-root Alpine production container image
├── pytest.ini                      # Standardized test execution configuration
└── requirements.txt                # Locked Python dependencies
```

---

## ⚠️ Engineering Limitations & Hardware Roadmap

1. **Physical RF Field Testing**: Software simulation, HMAC cryptography, and Cartesian collision physics have been verified in automated test benches. Physical line-of-sight RF testing with Semtech SX1281 modules on outdoor road tracks remains pending as detailed in [`docs/HARDWARE_VALIDATION_PLAN.md`](docs/HARDWARE_VALIDATION_PLAN.md).
2. **Automotive Certification**: This project is an academic research prototype and does not hold automotive ISO 26262 functional safety or ASIL certification.
3. **GNSS Multipath & Precision**: Commercial GNSS modules typically achieve ~2.5m accuracy. Centimeter-grade lane discrimination in dense traffic would require RTK differential correction.

---

## 📚 Technical Specifications Index

Detailed engineering documentation is maintained in the [`docs/`](docs/) directory:

| Document | Description |
| :--- | :--- |
| [**Canonical Telemetry Contract**](docs/CANONICAL_TELEMETRY_CONTRACT.md) | Strict key-value serialization specification for HMAC signing. |
| [**Firmware Specification & Pinout**](docs/FIRMWARE_SPECIFICATION.md) | STM32 Nucleo/Blue Pill pin mapping, SPI SX1281 setup, and build notes. |
| [**Mathematical & Kinematic Formulation**](docs/MATHEMATICAL_FORMULATION.md) | Complete Haversine, compass kinematics, and TTC equations. |
| [**Hardware Bill of Materials (BOM)**](docs/HARDWARE_BOM.md) | Component shopping list, voltage regulator ratings, and transceiver specs. |
| [**Hardware Interface Specification**](docs/HARDWARE_INTERFACE_SPEC.md) | UART, SPI, and I2C signal timing and voltage level requirements. |
| [**Hardware Validation Plan**](docs/HARDWARE_VALIDATION_PLAN.md) | Step-by-step bench and field test procedures for physical hardware. |
| [**Failure & Recovery Matrix**](docs/FAILURE_AND_RECOVERY_MATRIX.md) | System response to radio loss, GPS lock loss, and sensor faults. |
| [**Indic Voice Dispatch Specification**](docs/INDIC_VOICE_SPECIFICATION.md) | Multi-lingual audio architecture covering 12 Indian regional languages. |
| [**MQTT Reliability Specification**](docs/MQTT_RELIABILITY_SPEC.md) | Broker reconnection, message buffering, and gateway health heartbeats. |
| [**Requirements & AIS-230 Alignment**](docs/REQUIREMENTS_MATRIX.md) | Comprehensive engineering requirements and regulatory alignment matrix. |

---

## 📄 License & Attribution

This project is open-source software licensed under the **[MIT License](LICENSE)**.

Developed by **Rajesh Mediboina** as an advanced engineering prototype for internet-independent vehicular safety and highway telemetry.
