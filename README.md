# 🚗⚡ V2V-SCADA: Internet-Independent Vehicle-to-Vehicle Safety & Highway Telemetry System

> **Repository Description**: Internet-independent V2V communication and SCADA safety monitoring system using STM32, 2.4 GHz RF, GNSS, HMAC-SHA256 security, FastAPI, MQTT, and real-time telemetry visualization.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Hardware: STM32 + SX1281 2.4GHz](https://img.shields.io/badge/Hardware-STM32%20%7C%20SX1281%202.4GHz-brightgreen.svg)](docs/FIRMWARE_SPECIFICATION.md)
[![Standards: MoRTH AIS-230 Concepts](https://img.shields.io/badge/Standard-MoRTH%20AIS--230%20Concepts-orange.svg)](docs/REQUIREMENTS_MATRIX.md)
[![Backend: FastAPI / WebSockets](https://img.shields.io/badge/Backend-FastAPI%20%7C%20WebSockets%20%7C%20MQTT-009688.svg)](backend/)
[![Security: HMAC-SHA256 & RBAC](https://img.shields.io/badge/Security-HMAC--SHA256%20%7C%20RBAC%20%7C%20Anti--Replay-red.svg)](backend/security.py)
[![Tests: 87/87 Pytest Passed](https://img.shields.io/badge/Tests-87%2F87%20Passed-success.svg)](tests/)
[![CI: GitHub Actions](https://img.shields.io/badge/CI-GitHub%20Actions%20Passing-2088FF.svg)](.github/workflows/ci.yml)

---

## 📌 Executive Summary
**V2V-SCADA** is an internet-independent Vehicle-to-Vehicle (V2V) cooperative collision avoidance and highway supervisory telemetry system designed as a final-year engineering prototype aligned with concepts from India's **MoRTH AIS-230** framework. Operating without dependence on 4G/5G cellular towers or cloud infrastructure, the platform combines ARM Cortex-M (STM32) edge microcontrollers, 2.4 GHz RF transceivers, GNSS positioning, cryptographic HMAC-SHA256 integrity verification, deterministic Time-to-Collision (TTC) mathematics, and a real-time SCADA monitoring dashboard.

---

## ⚠️ Problem Statement
Multi-vehicle highway accidents frequently occur under **Non-Line-of-Sight (NLOS)** conditions—such as blind mountain turns, heavy rain, dust, and heavy transport vehicle obstruction. Traditional vehicle sensors (cameras, LiDAR, radar) require direct optical sightlines, while cellular C-V2X architectures fail in rural highway zones and mountain valleys where cell coverage is absent. **V2V-SCADA** addresses this by broadcasting low-latency, peer-to-peer RF telemetry directly between vehicles at 10 Hz, computing collision vectors autonomously on the microcontroller edge.

---

## 🏛️ System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│             CORE SAFETY PATH (100% Offline / Zero Cellular)            │
│                                                                        │
│   Vehicle Node A (STM32)                 Vehicle Node B (STM32)        │
│   [GNSS + IMU + Crypto]                  [GNSS + IMU + Crypto]         │
│             │                                      │                   │
│             └─── 2.4 GHz RF Direct (SX1281 FLRC) ──┘                   │
│                  (TTC Math, Audio Buzzer, Hazard OLED)                 │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │ Intercepted via RSU Gateway
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│            SCADA MONITORING WORKSTATION (Supervisory & Audit)          │
│                                                                        │
│   [Mosquitto MQTT Broker] ──► [FastAPI Backend Engine]                 │
│                                  │ (HMAC Verification, RBAC, SQLite)   │
│                                  ├──► 60 FPS WebSocket Telemetry Stream│
│                                  ├──► Leaflet Cybernetic HUD Dashboard │
│                                  └──► Automated PDF Incident Audits    │
└────────────────────────────────────────────────────────────────────────┘
```

### Architectural Tiers:
- **Core System (Essential)**: V2V telemetry, 2.4 GHz RF transceivers, GNSS positioning, 6-DoF IMU orientation, HMAC-SHA256 packet signatures, anti-replay windowing, deterministic TTC collision detection, and SCADA dashboard.
- **Supporting (Platform)**: Mosquitto MQTT broker, FastAPI async backend, WebSockets, SQLite in WAL mode, and Docker containerization.
- **Advanced / Optional (Modular)**: Machine Learning supplementary risk classification, WebRTC multi-lingual Indic voice translation, tollgate geofencing, and emergency service dispatch logs.

---

## 🔑 Key Features
- **Cellular & Cloud Independence**: Peer-to-peer RF communication functions in remote valleys, tunnels, and blind curves.
- **Sub-Second Collision Warnings**: Microcontroller edge evaluates closing speed and triggers multi-tier warnings (TTC $\le 5.0\text{s}$, $3.5\text{s}$, $2.5\text{s}$).
- **Cryptographic Defense-in-Depth**: HMAC-SHA256 signing, strict canonical serialization, 30-second timestamp windows, and monotonic sequence anti-replay reject rogue spoof attacks.
- **Role-Based Access Control (RBAC)**: Enforces role permissions (`viewer`, `operator`, `admin`) across state-mutating endpoints and SCADA command allowlisting.
- **Real-Time Highway Dashboard**: Live geospatial tracking, speed telemetry, heading ribbons, and instantaneous threat alerts over WebSockets.
- **12 Indian Languages Voice HUD**: In-browser speech recognition and translation with offline emergency phrase lookup.

---

## 🛡️ Security Architecture & RBAC

The system cleanly separates **Demo Mode** from **Secure Mode**:

| Feature / Setting | DEMO MODE (`DEMO_MODE=true`) | SECURE MODE (`DEMO_MODE=false`) |
| :--- | :--- | :--- |
| **API Authentication** | Optional (`API_AUTH_ENABLED=false`) | **Strictly Enforced** (`API_AUTH_ENABLED=true`) |
| **API Roles** | Unrestricted demo access | `viewer`, `operator`, `admin` enforced via Bearer/Key |
| **Mosquitto MQTT** | Anonymous local broker (`port 1883`) | TLS 1.2+ (`port 8883`), Username/Password + ACL |
| **HMAC Secret** | Default demo secret allowed | **Strict Check**: Rejects weak/default secrets at startup |
| **SCADA Commands** | Allowlisted (`TEST_ALARM`, etc.) | Allowlisted + Signed + Operator Role Required |
| **Path Traversal Protection** | Regex restricted to `.pdf` in reports/ | Regex restricted to `.pdf` in reports/ |

### SCADA Command Allowlist
Arbitrary shell command execution is prohibited. `POST /api/command` only accepts:
`EMERGENCY_ALERT`, `SLOW_DOWN`, `STOP_WARNING`, `YIELD_TO_EMERGENCY`, `TEST_ALARM`, `CLEAR_HAZARD`, `RESUME_NORMAL_SPEED`.

---

## 📐 Deterministic Collision Physics vs Supplementary ML

### Primary: Deterministic Physics
Collision risk is computed via geodesic Haversine distance and Cartesian relative closing velocity ($v_{close}$):
$$\text{Closing Velocity } v_{close} = \frac{dx \cdot rv_x + dy \cdot rv_y}{\text{distance}}, \quad \text{TTC} = \frac{\text{distance}}{v_{close}}$$
Details are documented in [`docs/MATHEMATICAL_FORMULATION.md`](docs/MATHEMATICAL_FORMULATION.md).

### Supplementary: Machine Learning Classifier
> [!IMPORTANT]
> The ML model is a supplementary collision-risk classifier trained and evaluated using synthetic kinematic data (generated across diverse relative speed, heading, and distance ranges). The deterministic TTC-based safety logic remains the primary safety-oriented mechanism. The ML model outputs a supplementary advisory classification with automatic fallback to deterministic physics if the model is absent or degraded.

---

## 💻 Technology Stack

- **Firmware**: C++ (Arduino / PlatformIO for STM32 ARM Cortex-M)
- **Backend**: Python 3.12, FastAPI, Uvicorn, WebSockets, Pydantic v2
- **Message Broker**: Eclipse Mosquitto MQTT
- **Database**: SQLite3 (Write-Ahead Logging mode)
- **Frontend HUD**: Vanilla HTML5, CSS3, JavaScript ES6, Leaflet.js (zero heavy framework dependencies)
- **Containerization**: Docker, Docker Compose (Alpine non-root containers)
- **Testing**: Pytest, Starlette TestClient, GitHub Actions CI

---

## 🚀 Quick Start Guide

### Option 1: Local Development (Demo Mode)

```bash
# 1. Clone the repository
git clone https://github.com/rajeshmediboina596-droid/V2V-SCADA.git
cd V2V-SCADA

# 2. Set up virtual environment
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start Mosquitto (or use built-in direct fallback)
# mosquitto -c mqtt/mosquitto.conf

# 5. Launch SCADA Central Backend
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser at **`http://127.0.0.1:8000`** to access the SCADA Dashboard HUD.

### Option 2: Docker Deployment

```bash
# Start Demo Stack (FastAPI + Mosquitto)
docker compose up -d

# Check container logs
docker compose logs -f
```

---

## 🧪 Testing & Verification

The repository contains **87 automated tests** across 7 test suites validating cryptographic security, collision physics, API boundaries, RBAC authorization, and fault recovery:

```bash
# Run complete test suite
pytest

# Compile all source files
python -m compileall -q .
```

### Test Suites Overview:
- `tests/test_auth_and_control_hardening.py`: RBAC permissions (viewer, operator, admin), SCADA command allowlist, query bounds, path traversal rejection.
- `tests/test_v2v_security_and_physics.py`: Cryptographic HMAC signatures, anti-replay, head-on/diverging collision physics, geofencing.
- `tests/test_security_regressions.py`: Field tampering attacks, expired timestamps, replayed sequence numbers, CORS headers.
- `tests/test_collision_scenarios.py`: 16 exhaustive multi-vehicle kinematic collision scenarios.
- `tests/test_canonical_contract.py`: Serialization boundaries and Pydantic constraints.
- `tests/test_failure_recovery.py`: Node reboots, network dropouts, degraded ML fallback.
- `tests/test_mqtt_reliability.py`: MQTT disconnect/reconnect callbacks, gateway health, telemetry bursts.

---

## ⚠️ Limitations & Hardware Testing Status

1. **Physical RF Range**: Software simulation and deterministic kinematics have been verified in test suites. Physical range measurements with Semtech SX1281 modules remain pending as documented in [`docs/HARDWARE_VALIDATION_PLAN.md`](docs/HARDWARE_VALIDATION_PLAN.md).
2. **Automotive Certification**: This project is an academic research prototype and does not hold automotive ISO 26262 or ASIL safety certification.
3. **GNSS Accuracy**: Commercial low-cost GNSS modules typically provide 2.5m CEP accuracy; multi-path mitigation or RTK would be required for centimetre-grade lane discrimination.

---

## 📚 Technical Documentation Index

Detailed engineering specifications are maintained in the [`docs/`](docs/) directory:
- [Canonical Telemetry Contract](docs/CANONICAL_TELEMETRY_CONTRACT.md)
- [Firmware Specification & Pinout](docs/FIRMWARE_SPECIFICATION.md)
- [Mathematical & Kinematic Formulation](docs/MATHEMATICAL_FORMULATION.md)
- [Hardware Bill of Materials (BOM)](docs/HARDWARE_BOM.md)
- [Hardware Interface Specification](docs/HARDWARE_INTERFACE_SPEC.md)
- [Hardware Validation Plan](docs/HARDWARE_VALIDATION_PLAN.md)
- [Failure & Recovery Matrix](docs/FAILURE_AND_RECOVERY_MATRIX.md)
- [Multi-Indian-Language Voice Dispatch](docs/INDIC_VOICE_SPECIFICATION.md)
- [MQTT Reliability Specification](docs/MQTT_RELIABILITY_SPEC.md)
- [Requirements & AIS-230 Alignment](docs/REQUIREMENTS_MATRIX.md)

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
