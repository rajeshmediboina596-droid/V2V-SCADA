# 🚗 V2V-SCADA — Real-Time Vehicle-to-Vehicle Safety Communication System

> A real-time, offline-capable Vehicle-to-Vehicle (V2V) communication and SCADA-based safety monitoring platform using **ESP32**, **GPS**, **HMAC-SHA256 Cryptography**, **Machine Learning**, and a live **Cyber-HUD Dashboard** — built to prevent collisions without any internet dependency.

---

## 📸 Dashboard Preview

The system features a full-screen SCADA HUD with real-time vehicle tracking on a dark map, live threat detection, speed matrix charts, and a Deep Packet Inspection (DPI) feed.

---

## 🌟 Key Features

| Feature | Description |
|---|---|
| 🗺️ **Live Map Tracking** | Vehicles appear as radar blips on an interactive dark map (Leaflet.js + CartoDB) with real-time GPS position updates |
| 💥 **Collision Prediction** | ML model (Random Forest) + Haversine physics engine calculates Time-To-Collision (TTC) and fires alerts |
| 🔐 **Cyber-Security** | Every V2V packet is verified with HMAC-SHA256. Rogue/spoofed packets are blocked and shown in the DPI feed |
| 🚨 **Emergency Vehicle Alerts** | Detects Emergency vehicles within 200m radius and triggers a YIELD RIGHT OF WAY alarm |
| 🚧 **Geofencing** | Configurable restricted zones. Any vehicle entering is flagged with a Geofence Breach alert |
| 📡 **V2I Traffic Light (SPaT)** | Simulates V2I Signal Phase and Timing (SPaT) interception showing countdown for Red/Green/Yellow |
| 🛰️ **GNSS/RTK Panel** | Live satellite count and HDOP accuracy readouts |
| 📊 **Speed Matrix Chart** | Real-time Chart.js speed graph plotting all active vehicles simultaneously |
| 🖥️ **DPI Feed** | Scrolling hex-dump feed of live encrypted V2V MQTT payloads |
| 🔁 **Predictive Trajectories** | Dotted lines showing where each vehicle will be 5 seconds in the future based on heading and speed |
| 📋 **PDF Report Export** | One-click SCADA session report generation via ReportLab |
| 🎮 **DEMO Mode** | Built-in physics simulation with 4 road-snapped vehicles for live demonstrations without hardware |
| ☠️ **Spoof Attack Simulator** | Button to inject a rogue HMAC-invalid packet and watch the DPI feed catch it in real time |
| 🚛 **Platooning Coordinator** | Detects when two vehicles are in convoy formation and displays aerodynamic drafting benefit |

---

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     EDGE LAYER (Hardware)                        │
│  ┌──────────┐         ┌──────────┐         ┌──────────┐         │
│  │  ESP32   │ ESP-NOW │  ESP32   │ ESP-NOW │  ESP32   │         │
│  │ Vehicle1 │◄───────►│ Vehicle2 │◄───────►│ RSU Node │──USB──► │
│  │ GPS+HMAC │         │ GPS+HMAC │         │(Laptop)  │         │
│  └──────────┘         └──────────┘         └──────────┘         │
└──────────────────────────────────────────────────────────────────┘
                                │ Serial/MQTT
┌──────────────────────────────────────────────────────────────────┐
│                   TRANSPORT LAYER (Local)                        │
│              Eclipse Mosquitto MQTT Broker (localhost:1883)      │
│              Topic: v2v/telemetry | v2v/alerts | v2v/commands    │
└──────────────────────────────────────────────────────────────────┘
                                │
┌──────────────────────────────────────────────────────────────────┐
│                    BACKEND LAYER (Python)                        │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ mqtt_client │  │ HMAC Verify  │  │   ML Collision Model   │  │
│  │  Subscriber │→ │  (Security)  │→ │ (Scikit-Learn RF Tree) │  │
│  └─────────────┘  └──────────────┘  └────────────────────────┘  │
│                          │                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │       FastAPI + WebSocket Server  (localhost:8000)       │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                                │ WebSocket
┌──────────────────────────────────────────────────────────────────┐
│                   FRONTEND LAYER (SCADA HUD)                     │
│    HTML5 + CSS3 + JavaScript + Leaflet.js + Chart.js             │
│       Dark Cyberpunk SCADA HUD @ http://localhost:8000           │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

### Software
| Layer | Technology |
|---|---|
| **Frontend** | HTML5, CSS3, Vanilla JavaScript |
| **Mapping** | Leaflet.js, CartoDB Dark Tiles, OSRM Road-Snapping |
| **Charts** | Chart.js |
| **Backend** | Python 3.12, FastAPI, Uvicorn |
| **Messaging** | Eclipse Mosquitto (MQTT Broker), Paho-MQTT |
| **Real-time** | WebSockets |
| **Machine Learning** | Scikit-Learn (Random Forest Classifier) |
| **Database** | SQLite |
| **PDF Reports** | ReportLab |
| **Containerisation** | Docker |

### Hardware (Physical Deployment)
| Component | Purpose |
|---|---|
| **ESP32 Dev Board** | Main microcontroller per vehicle |
| **U-blox NEO-M8N / NEO-6M** | High-precision GPS for Lat/Lon/Speed |
| **ESP-NOW Protocol** | Peer-to-peer wireless link between ESP32s (no internet, up to 200m) |
| **MPU-6050** | IMU for heading/yaw data and dead-reckoning fallback |
| **SSD1306 OLED** | Driver-facing display showing connection status |
| **Buzzer/LEDs** | Physical AEB (Automatic Emergency Braking) alert |
| **12V→5V Buck Converter** | Power from vehicle battery |

---

## 📂 Project Structure

```
V2V-SCADA/
│
├── backend/
│   ├── main.py              # FastAPI app, WebSocket server, API routes
│   ├── mqtt_client.py       # MQTT subscriber, HMAC verifier, collision engine
│   ├── database.py          # SQLite database init and logging
│   ├── report_generator.py  # PDF report generation via ReportLab
│   └── routes.json          # OSRM pre-computed road-snapped GPS paths
│
├── esp32/
│   ├── simulator.py         # PC-based 4-vehicle telemetry simulator (10Hz)
│   └── firmware/
│       └── main.ino         # Arduino/ESP32 firmware with HMAC-SHA256 signing
│
├── frontend/
│   ├── index.html           # Main SCADA HUD page
│   ├── css/style.css        # Full dark cyberpunk stylesheet
│   └── js/app.js            # Dashboard logic (map, charts, websocket, buttons)
│
├── ml/
│   ├── collision_model.py   # CollisionPredictor class (loads .pkl model)
│   ├── train_model.py       # Script to train and save the Random Forest model
│   └── collision_risk_model.pkl  # Pre-trained model file
│
├── mqtt/
│   ├── mosquitto.conf       # Mosquitto broker configuration (ports 1883, 8883)
│   ├── docker-compose.yml   # Docker Compose to run Mosquitto easily
│   ├── generate_certs.py    # Script to generate TLS certificates
│   ├── generate_certs.sh    # Shell version of cert generator
│   └── generate_certs.bat   # Windows batch version of cert generator
│
├── .gitignore
├── requirements.txt         # Python dependencies
└── README.md
```

---

## ⚙️ Local Setup & Installation

Follow these steps in order on a fresh machine to get everything running.

### Prerequisites
- [Python 3.10+](https://www.python.org/downloads/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for Mosquitto)
- [Git](https://git-scm.com/)

---

### Step 1 — Clone the Repository
```bash
git clone https://github.com/rajeshmediboina596-droid/V2V-SCADA.git
cd V2V-SCADA
```

---

### Step 2 — Start the MQTT Broker (Mosquitto via Docker)
Make sure Docker Desktop is **open and running**, then run this command from inside the project folder:

**Windows (PowerShell):**
```powershell
docker run -d --name mosquitto -p 1883:1883 -p 8883:8883 -v "%cd%\mqtt\mosquitto.conf:/mosquitto/config/mosquitto.conf" eclipse-mosquitto
```

**macOS / Linux:**
```bash
docker run -d --name mosquitto -p 1883:1883 -p 8883:8883 -v "$(pwd)/mqtt/mosquitto.conf:/mosquitto/config/mosquitto.conf" eclipse-mosquitto
```

> ✅ You only need to run this once. From the next time onwards, just use `docker start mosquitto` to bring it back up.

---

### Step 3 — Set Up the Python Environment
```bash
# Create virtual environment
python -m venv venv

# Activate it (Windows)
.\venv\Scripts\activate

# Activate it (macOS/Linux)
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
```

---

### Step 4 — Run the Backend Server
```bash
python backend/main.py
```
The SCADA dashboard is now live at 👉 **[http://localhost:8000](http://localhost:8000)**

---

### Step 5 — Run the Vehicle Simulator
Open a **second terminal** (activate the venv again), then run:
```bash
# Windows
.\venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

python esp32/simulator.py
```

You will now see 4 vehicles (V1, V2, V3, V4) moving on the map, triggering collision alerts and emergency vehicle warnings in real time.

---

## 📡 MQTT Topic Reference

| Topic | Direction | Description |
|---|---|---|
| `v2v/telemetry` | Vehicles → Backend | GPS telemetry + HMAC signature from each vehicle |
| `v2v/alerts/{vehicle_id}` | Backend → Vehicles | Collision warning or Emergency Yield alert for a specific vehicle |
| `v2v/commands` | Backend → All | Broadcast terminal command to all active V2V units |

---

## 🛡️ Security Model

Every vehicle payload is signed using **HMAC-SHA256** with a shared secret key before publishing to MQTT.

The backend's `mqtt_client.py` re-computes the expected signature for every incoming message and compares it using a constant-time comparison (`hmac.compare_digest`) to prevent timing attacks.

**If the signature is invalid:**
- The packet is **silently dropped** — it never reaches the dashboard or the database.
- A **`security_alert`** event is fired over WebSocket to the frontend.
- The HUD shows a **"🚨 CYBER-ATTACK BLOCKED"** card in the Threat Detection panel.
- The raw rogue payload appears in the **DPI Feed** marked as `[BLOCK] HMAC_FAIL`.

You can test this live by clicking the **`⚠️ SPOOF ATTACK`** button on the dashboard.

---

## 🧠 Machine Learning Model

The collision risk engine uses a **Scikit-Learn Random Forest Classifier** trained on distance (meters) and closing speed (m/s) features.

**Risk Levels:**
| Level | Meaning |
|---|---|
| `0` | ✅ Safe — no immediate threat |
| `1` | ⚠️ Warning — vehicles are converging |
| `2` | 🚨 Critical — imminent collision, AEB triggered |
| `4` | 🚑 Emergency Vehicle Yield — within 200m radius |

To retrain the model yourself:
```bash
python ml/train_model.py
```

---

## 🔌 ESP32 Hardware Flashing

To flash the firmware onto a physical ESP32:

1. Open `esp32/firmware/main.ino` in the **Arduino IDE**.
2. Install required libraries via the Library Manager:
   - `PubSubClient` (by Nick O'Leary)
   - `ArduinoJson` (by Benoit Blanchon)
3. Edit the credentials at the top of the file:
   ```cpp
   const char* ssid = "YOUR_WIFI_SSID";
   const char* password = "YOUR_WIFI_PASSWORD";
   const char* mqtt_server = "192.168.X.X"; // IP of machine running the backend
   const char* vehicle_id = "V1"; // Unique ID per vehicle
   ```
4. Select your ESP32 board from **Tools → Board → ESP32 Dev Module**.
5. Click **Upload**.

The ESP32 will now publish HMAC-signed GPS telemetry at 10Hz to your local MQTT broker.

---

## 🤝 Contributing

1. Fork this repository.
2. Create a new branch: `git checkout -b feature/your-feature-name`
3. Commit your changes: `git commit -m "feat: Add your feature"`
4. Push to GitHub: `git push origin feature/your-feature-name`
5. Open a Pull Request.

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).

---

<p align="center">Built with ❤️ for safer roads</p>
